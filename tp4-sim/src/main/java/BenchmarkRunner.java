import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * TP4 Benchmark – wall-clock time vs N, comparing brute-force O(N²) vs CIM O(N).
 *
 * Runs both modes for each N, averaging over multiple realizations.
 * Writes results_nocim.txt and results_cim.txt to the output directory.
 *
 * CLI:
 *   --tf   <double>  simulation time (default 5.0)
 *   --dt   <double>  integration step (default 0.01)
 *   --runs <int>     realizations per N (default 5)
 *   --k    <double>  elastic constant (default 1000.0)
 *   --bin  <path>    output dir (default ../tp4-bin/benchmark)
 */
public class BenchmarkRunner {

    static final int[] N_VALUES = {
        100, 200, 300, 400, 500, 600, 700, 800, 900, 1000
    };

    public static void main(String[] args) throws IOException {
        double tf   = 5.0;
        double dt   = 0.01;
        int    runs = 5;
        double k    = 1000.0;
        String bin  = resolveBin();

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--tf"   -> tf   = Double.parseDouble(args[++i]);
                case "--dt"   -> dt   = Double.parseDouble(args[++i]);
                case "--runs" -> runs = Integer.parseInt(args[++i]);
                case "--k"    -> k    = Double.parseDouble(args[++i]);
                case "--bin"  -> bin  = args[++i];
            }
        }

        Path outDir = Paths.get(bin);
        Files.createDirectories(outDir);
        Path tmp = outDir.resolve("_tmp");

        System.out.printf("# TP4 Benchmark  tf=%.1f  dt=%.2e  runs=%d%n", tf, dt, runs);
        System.out.println("# N  brute_s  cim_s");

        try (PrintWriter wNoCim = new PrintWriter(Files.newBufferedWriter(outDir.resolve("results_nocim.txt")));
             PrintWriter wCim   = new PrintWriter(Files.newBufferedWriter(outDir.resolve("results_cim.txt")))) {

            wNoCim.println("N wall_time_s");
            wCim  .println("N wall_time_s");

            for (int n : N_VALUES) {
                // warm-up (both modes)
                TimeDrivenMD.run(n, 0L, dt, 0.1, 1.0, k, 0, true, true, false, tmp);
                TimeDrivenMD.run(n, 0L, dt, 0.1, 1.0, k, 0, true, true, true,  tmp);

                double totalBrute = 0, totalCim = 0;
                for (int r = 0; r < runs; r++) {
                    long t0 = System.nanoTime();
                    TimeDrivenMD.run(n, r, dt, tf, tf + 1, k, 0, true, true, false, tmp);
                    totalBrute += (System.nanoTime() - t0) / 1e9;

                    t0 = System.nanoTime();
                    TimeDrivenMD.run(n, r, dt, tf, tf + 1, k, 0, true, true, true, tmp);
                    totalCim += (System.nanoTime() - t0) / 1e9;
                }

                double avgBrute = totalBrute / runs;
                double avgCim   = totalCim   / runs;
                System.out.printf("%4d  brute=%.4f s  cim=%.4f s  speedup=%.2fx%n",
                        n, avgBrute, avgCim, avgBrute / avgCim);
                wNoCim.printf("%d %.6f%n", n, avgBrute);
                wCim  .printf("%d %.6f%n", n, avgCim);
                wNoCim.flush();
                wCim  .flush();
            }
        }

        // cleanup temp dir
        if (Files.isDirectory(tmp))
            Files.walk(tmp).sorted(Comparator.reverseOrder()).map(Path::toFile).forEach(File::delete);

        System.out.printf("Results → %s%n", outDir);
    }

    static String resolveBin() {
        String env = System.getenv("TP4_BIN_PATH");
        if (env != null && !env.isEmpty()) return env + "/benchmark";
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp4-bin/benchmark").toAbsolutePath().normalize().toString();
    }
}
