/*
 * External-sampling MCCFR (Lanctot et al. 2009) with linear weighting, over the
 * abstract betting tree and bucketed deal pool written by tools/cfr_train.py.
 *
 *   mccfr TREE DEALS STATE ITERATIONS THREADS SEED
 *
 * STATE holds regrets and strategy sums; it is resumed when it exists and
 * rewritten at the end, together with STATE.strategy (normalized average
 * strategy, float32, in tree offset order). Threads update shared tables
 * without locks; the occasional lost update does not matter.
 */
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum { DECISION, FOLD_END, SHOWDOWN };
typedef struct { int32_t kind, player, street, nact, child0, offset, value; } Node;

static Node *nodes;
static int32_t *children;
static int64_t size;
static float *regret;
static double *avg;
static uint16_t *buckets;
static int8_t *result;
static int32_t n_nodes;
static int64_t n_deals, target, done0;
static int64_t counter;

static uint64_t next(uint64_t *s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static double unif(uint64_t *s) { return (next(s) >> 11) * (1.0 / 9007199254740992.0); }

static void current(const float *r, int na, double *s) {
    double tot = 0;
    for (int a = 0; a < na; a++) tot += s[a] = r[a] > 0 ? r[a] : 0;
    for (int a = 0; a < na; a++) s[a] = tot > 0 ? s[a] / tot : 1.0 / na;
}

/* Value for `trav` (seat) of the subtree at node n. */
static double walk(int n, const uint16_t *b, int res, int trav, double w, uint64_t *rs) {
    const Node *nd = &nodes[n];
    if (nd->kind == FOLD_END) return trav == 0 ? nd->value : -nd->value;
    if (nd->kind == SHOWDOWN) return (trav == 0 ? res : -res) * (double)nd->value;
    int na = nd->nact, p = nd->player;
    int64_t base = nd->offset + (int64_t)b[p * 4 + nd->street] * na;
    float *r = regret + base;
    double s[8];
    current(r, na, s);
    if (p == trav) {
        double u[8], ev = 0;
        for (int a = 0; a < na; a++) ev += s[a] * (u[a] = walk(children[nd->child0 + a], b, res, trav, w, rs));
        for (int a = 0; a < na; a++) r[a] += (float)(w * (u[a] - ev));
        return ev;
    }
    double *g = avg + base, x = unif(rs);
    for (int a = 0; a < na; a++) g[a] += w * s[a];
    int a = 0;
    while (a < na - 1 && (x -= s[a]) > 0) a++;
    return walk(children[nd->child0 + a], b, res, trav, w, rs);
}

static void *worker(void *arg) {
    uint64_t rs = (uint64_t)(uintptr_t)arg;
    for (;;) {
        int64_t start = __atomic_fetch_add(&counter, 1000, __ATOMIC_RELAXED);
        if (start >= target) return NULL;
        double w = 1.0 + (done0 + start) / 1e6;  /* linear CFR weighting */
        for (int64_t i = start; i < start + 1000 && i < target; i++) {
            int64_t d = next(&rs) % n_deals;
            for (int trav = 0; trav < 2; trav++) walk(0, buckets + 8 * d, result[d], trav, w, &rs);
        }
    }
}

static void *read_file(const char *path, long *len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    *len = ftell(f);
    fseek(f, 0, SEEK_SET);
    void *buf = malloc(*len);
    if (fread(buf, 1, *len, f) != (size_t)*len) { perror(path); exit(1); }
    fclose(f);
    return buf;
}

/* Write STATE (iterations, regrets, sums) and STATE.strategy (normalized average strategy).
   Each decision's block (offset + bucket * nact + action) runs to the next decision's offset,
   since offsets were assigned in node order. Unvisited infosets fall back to the current
   regret-matching strategy. Called while threads run too: a slightly torn snapshot is fine. */
static void save(const char *state, int64_t done) {
    char tmp[4096], path[4096];
    snprintf(tmp, sizeof tmp, "%s.tmp", state);
    FILE *f = fopen(tmp, "wb");
    fwrite(&done, 8, 1, f);
    fwrite(regret, sizeof(float), size, f);
    fwrite(avg, sizeof(double), size, f);
    fclose(f);
    rename(tmp, state);

    float *out = malloc(size * sizeof(float));
    int64_t prev = -1;
    int prev_na = 0;
    for (int32_t n = 0; n <= n_nodes; n++) {
        int64_t off = n < n_nodes ? (nodes[n].kind == DECISION ? nodes[n].offset : -1) : size;
        if (off < 0) continue;
        if (prev >= 0) {
            for (int64_t i = prev; i < off; i += prev_na) {
                double tot = 0, s[8];
                for (int a = 0; a < prev_na; a++) tot += avg[i + a];
                if (tot > 0) {
                    for (int a = 0; a < prev_na; a++) out[i + a] = (float)(avg[i + a] / tot);
                } else {
                    current(regret + i, prev_na, s);
                    for (int a = 0; a < prev_na; a++) out[i + a] = (float)s[a];
                }
            }
        }
        if (n < n_nodes) { prev = off; prev_na = nodes[n].nact; }
    }
    snprintf(tmp, sizeof tmp, "%s.strategy.tmp", state);
    snprintf(path, sizeof path, "%s.strategy", state);
    f = fopen(tmp, "wb");
    fwrite(out, sizeof(float), size, f);
    fclose(f);
    rename(tmp, path);
    free(out);
    fprintf(stderr, "saved after %lld iterations\n", (long long)done);
}

int main(int argc, char **argv) {
    if (argc != 7) { fprintf(stderr, "usage: mccfr TREE DEALS STATE ITERATIONS THREADS SEED\n"); return 1; }
    long len;
    char *t = read_file(argv[1], &len);
    if (!t) { perror(argv[1]); return 1; }
    n_nodes = ((int32_t *)t)[0];
    int32_t n_children = ((int32_t *)t)[1];
    memcpy(&size, t + 8, 8);
    nodes = (Node *)(t + 16);
    children = (int32_t *)(t + 16 + (int64_t)n_nodes * sizeof(Node));
    (void)n_children;

    char *dl = read_file(argv[2], &len);
    if (!dl) { perror(argv[2]); return 1; }
    memcpy(&n_deals, dl, 8);
    buckets = (uint16_t *)(dl + 8);  /* n x 2 seats x 4 streets */
    result = (int8_t *)(dl + 8 + 16 * n_deals);

    regret = calloc(size, sizeof(float));
    avg = calloc(size, sizeof(double));
    FILE *f = fopen(argv[3], "rb");
    if (f) {
        if (fread(&done0, 8, 1, f) != 1 || fread(regret, sizeof(float), size, f) != (size_t)size ||
            fread(avg, sizeof(double), size, f) != (size_t)size) { fprintf(stderr, "bad state file\n"); return 1; }
        fclose(f);
        fprintf(stderr, "resumed after %lld iterations\n", (long long)done0);
    }

    target = atoll(argv[4]);
    int threads = atoi(argv[5]);
    uint64_t seed = strtoull(argv[6], NULL, 10);
    pthread_t th[256];
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < threads; i++) {
        uint64_t s = seed * 1000003ULL + i;
        next(&s);
        pthread_create(&th[i], NULL, worker, (void *)(uintptr_t)s);
    }
    for (int tick = 1;; tick++) {
        struct timespec ts = {1, 0};
        nanosleep(&ts, NULL);
        int64_t c = __atomic_load_n(&counter, __ATOMIC_RELAXED);
        if (c >= target) break;
        if (tick % 30 == 0) {
            clock_gettime(CLOCK_MONOTONIC, &t1);
            double el = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
            fprintf(stderr, "%lld / %lld iterations, %.0f s, %.0f it/s\n", (long long)c, (long long)target, el, c / el);
        }
        if (tick % 120 == 0) save(argv[3], done0 + c);
    }
    for (int i = 0; i < threads; i++) pthread_join(th[i], NULL);
    save(argv[3], done0 + target);
    return 0;
}
