import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * TP4 Benchmark – wall-clock time vs N, comparing brute-force O(N²) vs CIM O(N).
 *
 * Runs both modes (or CIM only) for each N, averaging over multiple realizations.
 * Writes results_nocim.txt and/or results_cim.txt to the output directory.
 *
 * CLI:
 *   --tf      <double>  simulation time (default 5.0)
 *   --dt      <double>  integration step (default 0.001)
 *   --runs    <int>     realizations per N (default 5)
 *   --k       <double>  elastic constant (default 1000.0)
 *   --n-min   <int>     minimum N (default 100)
 *   --n-max   <int>     maximum N (default 1000)
 *   --n-step  <int>     N step size (default 100)
 *   --cim-only          skip brute-force, only run CIM
 *   --bin     <path>    output dir (default ../tp4-bin/benchmark)
 */
public class BenchmarkRunner {

    public static void main(String[] args) throws IOException {
        double  tf      = 5.0;
        double  dt      = 0.001;
        int     runs    = 5;
        double  k       = 1000.0;
        int     nMin    = 100;
        int     nMax    = 1000;
        int     nStep   = 100;
        boolean cimOnly = false;
        String  bin     = resolveBin();

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--tf"      -> tf      = Double.parseDouble(args[++i]);
                case "--dt"      -> dt      = Double.parseDouble(args[++i]);
                case "--runs"    -> runs    = Integer.parseInt(args[++i]);
                case "--k"       -> k       = Double.parseDouble(args[++i]);
                case "--n-min"   -> nMin    = Integer.parseInt(args[++i]);
                case "--n-max"   -> nMax    = Integer.parseInt(args[++i]);
                case "--n-step"  -> nStep   = Integer.parseInt(args[++i]);
                case "--cim-only"-> cimOnly = true;
                case "--bin"     -> bin     = args[++i];
            }
        }

        // Build N array from range
        int count = (nMax - nMin) / nStep + 1;
        int[] nValues = new int[count];
        for (int i = 0; i < count; i++) nValues[i] = nMin + i * nStep;

        Path outDir = Paths.get(bin);
        Files.createDirectories(outDir);
        Path tmp = outDir.resolve("_tmp");

        System.out.printf("# TP4 Benchmark  tf=%.1f  dt=%.2e  runs=%d  cimOnly=%b%n",
                tf, dt, runs, cimOnly);
        System.out.println("# N  brute_s  cim_s");

        PrintWriter wNoCim = cimOnly ? null :
                new PrintWriter(Files.newBufferedWriter(outDir.resolve("results_nocim.txt")));
        PrintWriter wCim = new PrintWriter(Files.newBufferedWriter(outDir.resolve("results_cim.txt")));

        try {
            if (!cimOnly) wNoCim.println("N wall_time_s");
            wCim.println("N wall_time_s");

            for (int n : nValues) {
                // warm-up
                if (!cimOnly)
                    TimeDrivenMD.run(n, 0L, dt, 0.1, 1.0, k, 0, true, true, false, tmp);
                TimeDrivenMD.run(n, 0L, dt, 0.1, 1.0, k, 0, true, true, true, tmp);

                double totalBrute = 0, totalCim = 0;
                for (int r = 0; r < runs; r++) {
                    if (!cimOnly) {
                        long t0 = System.nanoTime();
                        TimeDrivenMD.run(n, r, dt, tf, tf + 1, k, 0, true, true, false, tmp);
                        totalBrute += (System.nanoTime() - t0) / 1e9;
                    }
                    long t0 = System.nanoTime();
                    TimeDrivenMD.run(n, r, dt, tf, tf + 1, k, 0, true, true, true, tmp);
                    totalCim += (System.nanoTime() - t0) / 1e9;
                }

                double avgCim = totalCim / runs;
                if (!cimOnly) {
                    double avgBrute = totalBrute / runs;
                    System.out.printf("%4d  brute=%.4f s  cim=%.4f s  speedup=%.2fx%n",
                            n, avgBrute, avgCim, avgBrute / avgCim);
                    wNoCim.printf("%d %.6f%n", n, avgBrute);
                    wNoCim.flush();
                } else {
                    System.out.printf("%4d  cim=%.4f s%n", n, avgCim);
                }
                wCim.printf("%d %.6f%n", n, avgCim);
                wCim.flush();
            }
        } finally {
            if (wNoCim != null) wNoCim.close();
            wCim.close();
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
