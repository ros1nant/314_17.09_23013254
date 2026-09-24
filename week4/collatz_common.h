#ifndef COLLATZ_COMMON_H
#define COLLATZ_COMMON_H

#include <ctype.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <omp.h>

#define CHECKSUM_MOD UINT64_C(1000000007)
#define MAX_THREADS 1024

typedef struct {
    double seconds;
    uint32_t max_steps;
    uint64_t checksum;
    uint64_t hits;
    int threads;
} Result;

static inline uint32_t collatz_steps(uint64_t n) {
    uint32_t steps = 0;
    while (n > 1) {
        if ((n & 1) == 0) n >>= 1;
        else n = 3 * n + 1;
        ++steps;
    }
    return steps;
}

static inline uint64_t workload_from_id(const char *id) {
    size_t length = strlen(id);
    if (length < 4 || length > 64) {
        fprintf(stderr, "Student ID must contain 4 to 64 decimal digits.\n");
        exit(EXIT_FAILURE);
    }
    for (size_t i = 0; i < length; ++i) {
        if (!isdigit((unsigned char)id[i])) {
            fprintf(stderr, "Student ID must contain decimal digits only.\n");
            exit(EXIT_FAILURE);
        }
    }
    return UINT64_C(10000000) + strtoull(id + length - 4, NULL, 10) * 1000;
}

static inline Result sequential(uint64_t n) {
    uint32_t maximum = 0;
    uint64_t sum = 0, hits = 0;
    double start = omp_get_wtime();
    for (uint64_t i = 1; i <= n; ++i) {
        uint32_t steps = collatz_steps(i);
        if (steps > maximum) maximum = steps;
        sum += steps;
        hits += steps > 100;
    }
    /* For the ID-derived N <= 19,999,000, the sum fits uint64_t.
       Reducing modulo once gives the same checksum as doing it each step. */
    Result result = {omp_get_wtime() - start, maximum,
                     sum % CHECKSUM_MOD, hits, 1};
    return result;
}

static inline int same_answer(Result a, Result b) {
    return a.max_steps == b.max_steps && a.checksum == b.checksum && a.hits == b.hits;
}

#endif
