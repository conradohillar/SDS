/**
 * Benchmark runner for TP3 Sistema 1 (análisis 1.1).
 *
 * Runs the event-driven simulation for a fixed tf = 5 s over a range of N values,
 * measuring wall-clock execution time. Outputs "N time_s" rows to stdout.
 *
 * Usage: mvn exec:java -Dexec.mainClass=BenchmarkRunner
 *        mvn exec:java -Dexec.mainClass=BenchmarkRunner "-Dexec.args=--tf 5 --runs 3"
 *
 * Flags:
 *   --tf   <double>  simulation end time per run (default 5)
 *   --runs <int>     repetitions per N value for averaging (default 3)
 */
public class BenchmarkRunner {

    static final int[] N_VALUES = buildRange(50, 800, 25);

    static int[] buildRange(int start, int end, int step) {
        int count = (end - start) / step + 1;
        int[] a = new int[count];
        for (int i = 0; i < count; i++) a[i] = start + i * step;
        return a;
    }

    public static void main(String[] args) throws Exception {
        double tf   = 5.0;
        int    runs = 3;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--tf"   -> tf   = Double.parseDouble(args[++i]);
                case "--runs" -> runs = Integer.parseInt(args[++i]);
            }
        }

        System.out.println("N wall_time_s");
        for (int n : N_VALUES) {
            double total = 0;
            for (int r = 0; r < runs; r++) {
                long start = System.nanoTime();
                var sim = new EventDrivenMD(n, 42L + r);
                sim.run(tf, null, null, 0, 1);
                total += (System.nanoTime() - start) / 1e9;
            }
            System.out.printf("%d %.6f%n", n, total / runs);
            System.out.flush();
        }
    }
}
