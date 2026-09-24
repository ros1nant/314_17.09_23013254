/* Build: gcc -O2 -fopenmp -std=c11 -Wall -Wextra collatz_seq.c -o collatz_seq
   Run:   ./collatz_seq YOUR_NUMERIC_STUDENT_ID
   Windows: .\collatz_seq.exe YOUR_NUMERIC_STUDENT_ID
   The full automated lab (collatz.c) uses this same sequential function. */
#include "collatz_common.h"

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s STUDENT_ID\n", argv[0]);
        return EXIT_FAILURE;
    }
    uint64_t n = workload_from_id(argv[1]);
    Result first = {0};
    double measured = 0;
    printf("Student ID: %s | N: %" PRIu64 "\n", argv[1], n);
    for (int run = 1; run <= 3; ++run) {
        Result result = sequential(n);
        if (run == 1) first = result;
        else if (!same_answer(first, result)) {
            fprintf(stderr, "Sequential results changed between runs.\n");
            return EXIT_FAILURE;
        }
        if (run > 1) measured += result.seconds;
        printf("Run %d%s: %.9f s | max=%" PRIu32
               " | checksum=%" PRIu64 " | hits>100=%" PRIu64 "\n",
               run, run == 1 ? " (discard warm-up)" : "", result.seconds,
               result.max_steps, result.checksum, result.hits);
    }
    printf("T_seq = (Run 2 + Run 3) / 2 = %.9f s\n", measured / 2);
    return EXIT_SUCCESS;
}
