/* Week 4: Amdahl Reality Gap, native C/OpenMP.
   Build: gcc -O2 -fopenmp -std=c11 -Wall -Wextra collatz.c -o collatz
   Run: ./collatz STUDENT_ID PHYSICAL_CORES EXISTING_OUTPUT_DIRECTORY
   Windows: .\collatz.exe STUDENT_ID PHYSICAL_CORES EXISTING_OUTPUT_DIRECTORY
   Other modes: --info, --self-test
   Requires collatz_common.h beside this file. Normal runs write results.csv
   and thread_profiles.csv in the specified directory (overwriting those names).
   run_lab.ps1 creates a fresh directory for every run. */
#include "collatz_common.h"
#include <errno.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

typedef struct {
    uint64_t iterations, steps;
    double active_seconds;
} ThreadProfile;

static Result parallel_run(uint64_t n, int threads, int naive,
                           omp_sched_t schedule, int chunk,
                           ThreadProfile *profiles) {
    /* volatile ensures GCC cannot hoist the deliberately shared-line writes
       into registers. Each thread owns a distinct int: there is no data race.
       The measured difference also includes memory writes vs register reduction. */
    _Alignas(64) volatile int hit_count[MAX_THREADS] = {0};
    uint32_t maximum = 0;
    uint64_t sum = 0, hits = 0;
    int actual_threads = 0;
    omp_set_schedule(schedule, chunk);
    double start = omp_get_wtime();
    #pragma omp parallel num_threads(threads) reduction(max:maximum) reduction(+:sum,hits)
    {
        int tid = omp_get_thread_num();
        uint64_t local_iterations = 0, local_steps = 0;
        #pragma omp single
        actual_threads = omp_get_num_threads();
        double thread_start = profiles ? omp_get_wtime() : 0;
        #pragma omp for schedule(runtime) nowait
        for (uint64_t i = 1; i <= n; ++i) {
            uint32_t steps = collatz_steps(i);
            if (steps > maximum) maximum = steps;
            sum += steps;
            if (steps > 100) {
                if (naive) ++hit_count[tid];
                else ++hits;
            }
            if (profiles) {
                ++local_iterations;
                local_steps += steps;
            }
        }
        if (profiles) {
            profiles[tid].iterations = local_iterations;
            profiles[tid].steps = local_steps;
            profiles[tid].active_seconds = omp_get_wtime() - thread_start;
        }
    }
    if (naive) {
        for (int t = 0; t < actual_threads; ++t) hits += hit_count[t];
    }
    Result result = {omp_get_wtime() - start, maximum,
                     sum % CHECKSUM_MOD, hits, actual_threads};
    return result;
}

static void print_info(void) {
    printf("Compiler: %s\nOpenMP macro: %d\n", __VERSION__, _OPENMP);
    printf("omp_get_num_procs: %d\nomp_get_max_threads: %d\n",
           omp_get_num_procs(), omp_get_max_threads());
    printf("omp_get_thread_limit: %d\nTimer tick seconds: %.12g\n",
           omp_get_thread_limit(), omp_get_wtick());
#ifdef _WIN32
    DWORD bytes = 0;
    GetLogicalProcessorInformation(NULL, &bytes);
    SYSTEM_LOGICAL_PROCESSOR_INFORMATION *info = malloc(bytes);
    if (info && GetLogicalProcessorInformation(info, &bytes)) {
        size_t count = bytes / sizeof(*info);
        for (size_t i = 0; i < count; ++i) {
            if (info[i].Relationship == RelationCache) {
                CACHE_DESCRIPTOR c = info[i].Cache;
                printf("Windows cache: level=%u type=%d size_bytes=%lu line_bytes=%u\n",
                       (unsigned)c.Level, (int)c.Type, (unsigned long)c.Size,
                       (unsigned)c.LineSize);
            }
        }
    } else {
        puts("Cache line query unavailable: verify from CPU documentation.");
    }
    free(info);
#endif
}

static void utc_now(char *out, size_t size) {
    time_t now = time(NULL);
    struct tm *utc = gmtime(&now);
    if (!utc || !strftime(out, size, "%Y-%m-%dT%H:%M:%SZ", utc)) {
        fprintf(stderr, "Cannot obtain UTC timestamp.\n");
        exit(EXIT_FAILURE);
    }
}

static FILE *open_output(const char *directory, const char *name) {
    char path[2048];
    int length = snprintf(path, sizeof(path), "%s/%s", directory, name);
    if (length < 0 || (size_t)length >= sizeof(path)) {
        fprintf(stderr, "Output path is too long.\n");
        exit(EXIT_FAILURE);
    }
    FILE *file = fopen(path, "w");
    if (!file) { perror(path); exit(EXIT_FAILURE); }
    return file;
}

static Result benchmark(FILE *csv, const char *id, uint64_t n,
                        const char *experiment, const char *variant,
                        const char *schedule_name, omp_sched_t schedule,
                        int chunk, int threads, int naive, int seq,
                        const Result *expected) {
    Result first = {0};
    for (int run = 1; run <= 3; ++run) {
        char timestamp[32];
        utc_now(timestamp, sizeof(timestamp));
        Result r = seq ? sequential(n) : parallel_run(n, threads, naive, schedule, chunk, NULL);
        if (run == 1) first = r;
        if (!same_answer(first, r) || (expected && !same_answer(*expected, r)) ||
            r.threads != threads || r.seconds <= 0) {
            fprintf(stderr, "FAILED validation: %s/%s, requested %d, actual %d.\n",
                    experiment, variant, threads, r.threads);
            exit(EXIT_FAILURE);
        }
        fprintf(csv, "%s,%s,%s,%d,%d,%d,%d,%d,%.9f,%" PRIu32
                ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%s,%s\n",
                experiment, variant, schedule_name, chunk, threads, r.threads,
                run, run == 1, r.seconds, r.max_steps, r.checksum, r.hits,
                n, id, timestamp);
        if (fflush(csv) != 0) { perror("Writing results.csv"); exit(EXIT_FAILURE); }
        printf("%-13s %-13s threads=%3d run=%d%s %.6f s max=%" PRIu32
               " checksum=%" PRIu64 " hits=%" PRIu64 "\n",
               experiment, variant, threads, run, run == 1 ? " warm-up" : "        ",
               r.seconds, r.max_steps, r.checksum, r.hits);
        fflush(stdout);
    }
    return first;
}

static int self_test(void) {
    if (collatz_steps(1) != 0 || collatz_steps(2) != 1 ||
        collatz_steps(26) != 10 || collatz_steps(27) != 111) return EXIT_FAILURE;
    Result known = sequential(27);
    if (known.max_steps != 111 || known.checksum != 387 || known.hits != 1) return EXIT_FAILURE;
    Result expected = sequential(10000);
    omp_sched_t schedules[] = {omp_sched_static, omp_sched_static, omp_sched_dynamic,
                              omp_sched_dynamic, omp_sched_guided};
    int chunks[] = {0, 1000, 100, 10000, 0};
    for (int k = 1; k <= 4; k *= 2) {
        for (int s = 0; s < 5; ++s) {
            for (int naive = 0; naive <= 1; ++naive) {
                ThreadProfile profiles[4] = {{0}};
                Result r = parallel_run(10000, k, naive, schedules[s], chunks[s], profiles);
                uint64_t iterations = 0, sum = 0;
                for (int t = 0; t < r.threads; ++t) {
                    iterations += profiles[t].iterations;
                    sum += profiles[t].steps;
                }
                if (!same_answer(expected, r) || iterations != 10000 ||
                    sum % CHECKSUM_MOD != expected.checksum || r.threads != k) return EXIT_FAILURE;
            }
        }
    }
    puts("Self-test PASS: known Collatz values and all five schedules, both counters, 1/2/4 threads.");
    puts("Small correctness test only; no submission measurements were generated.");
    return EXIT_SUCCESS;
}

int main(int argc, char **argv) {
    omp_set_dynamic(0);
    if (argc == 2 && strcmp(argv[1], "--info") == 0) { print_info(); return 0; }
    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) return self_test();
    if (argc != 4) {
        fprintf(stderr, "Usage: %s STUDENT_ID PHYSICAL_CORES EXISTING_OUTPUT_DIRECTORY\n", argv[0]);
        return EXIT_FAILURE;
    }
    uint64_t n = workload_from_id(argv[1]);
    char *end;
    errno = 0;
    long physical_long = strtol(argv[2], &end, 10);
    int logical = omp_get_num_procs();
    if (errno || end == argv[2] || *end || physical_long < 1 ||
        physical_long > logical || logical > MAX_THREADS || logical > omp_get_thread_limit()) {
        fprintf(stderr, "Invalid physical core count or unsupported OpenMP thread limit.\n");
        return EXIT_FAILURE;
    }
    int physical = (int)physical_long;
    printf("Student ID=%s N=%" PRIu64 " physical=%d logical_available=%d\n",
           argv[1], n, physical, logical);
    print_info();
    FILE *csv = open_output(argv[3], "results.csv");
    fprintf(csv, "experiment,variant,schedule,chunk,requested_threads,actual_threads,run,warmup,seconds,max_steps,checksum,hits_gt_100,n,student_id,utc_start\n");
    Result expected = benchmark(csv, argv[1], n, "sequential", "sequential", "none",
                                omp_sched_static, 0, 1, 0, 1, NULL);
    /* Include the worksheet powers of two and BOTH hardware boundaries for Q2. */
    for (int k = 1; k <= logical; ++k) {
        if (k == 1 || k == 2 || k == 4 || k == 8 || k == 16 || k == physical || k == logical) {
            benchmark(csv, argv[1], n, "scaling", "reduction", "static",
                      omp_sched_static, 0, k, 0, 0, &expected);
        }
    }
    benchmark(csv, argv[1], n, "false_sharing", "naive", "static",
              omp_sched_static, 0, physical, 1, 0, &expected);
    benchmark(csv, argv[1], n, "false_sharing", "reduction", "static",
              omp_sched_static, 0, physical, 0, 0, &expected);
    const char *names[] = {"static", "static_1000", "dynamic_100", "dynamic_10000", "guided"};
    const char *kinds[] = {"static", "static", "dynamic", "dynamic", "guided"};
    omp_sched_t schedules[] = {omp_sched_static, omp_sched_static, omp_sched_dynamic,
                              omp_sched_dynamic, omp_sched_guided};
    int chunks[] = {0, 1000, 100, 10000, 0};
    for (int s = 0; s < 5; ++s) {
        benchmark(csv, argv[1], n, "scheduling", names[s], kinds[s],
                  schedules[s], chunks[s], logical, 0, 0, &expected);
    }
    if (fclose(csv) != 0) { perror("Closing results.csv"); return EXIT_FAILURE; }
    /* Separate diagnostic passes: per-thread bookkeeping does not affect Table 3. */
    FILE *profile_csv = open_output(argv[3], "thread_profiles.csv");
    fprintf(profile_csv, "variant,threads,thread_id,iterations,total_collatz_steps,active_seconds\n");
    ThreadProfile *profiles = calloc((size_t)logical, sizeof(*profiles));
    if (!profiles) { perror("Allocating profiles"); return EXIT_FAILURE; }
    for (int s = 0; s < 5; ++s) {
        memset(profiles, 0, (size_t)logical * sizeof(*profiles));
        Result r = parallel_run(n, logical, 0, schedules[s], chunks[s], profiles);
        if (!same_answer(expected, r) || r.threads != logical) {
            fprintf(stderr, "Scheduling profile validation failed.\n");
            return EXIT_FAILURE;
        }
        for (int t = 0; t < logical; ++t) {
            fprintf(profile_csv, "%s,%d,%d,%" PRIu64 ",%" PRIu64 ",%.9f\n",
                    names[s], logical, t, profiles[t].iterations,
                    profiles[t].steps, profiles[t].active_seconds);
        }
        printf("Diagnostic profile complete: %s\n", names[s]);
        fflush(stdout);
    }
    free(profiles);
    if (fclose(profile_csv) != 0) { perror("Closing profiles"); return EXIT_FAILURE; }
    puts("All measurements complete. Checksums, maxima and hit counts match the sequential baseline.");
    return EXIT_SUCCESS;
}
