import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * TP4 Benchmark – wall-clock time vs N for Time-Driven MD.
 *
 * Runs TimeDrivenMD.run() (no I/O) for each N value, averaging over
 * multiple realizations. Prints "N time_s" pairs to stdout.
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
        50, 75, 100, 125, 150, 175, 200, 250, 300, 350, 400, 450, 500
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

        System.out.printf("# TP4 Benchmark  tf=%.1f  dt=%.2e  runs=%d%n", tf, dt, runs);
        System.out.println("# N  wall_time_s");

        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(outDir.resolve("results.txt")))) {
            w.println("N wall_time_s");

            for (int n : N_VALUES) {
                // warm-up
                Path tmp = outDir.resolve("_tmp");
                TimeDrivenMD.run(n, 0L, dt, 0.1, 1.0, k, 0, true, true, tmp);

                double total = 0;
                for (int r = 0; r < runs; r++) {
                    long t0 = System.nanoTime();
                    TimeDrivenMD.run(n, r, dt, tf, tf + 1, k, 0, true, true, tmp);
                    total += (System.nanoTime() - t0) / 1e9;
                }
                double avg = total / runs;
                System.out.printf("%d %.4f%n", n, avg);
                w.printf("%d %.6f%n", n, avg);
                w.flush();
            }
        }

        // cleanup temp dir
        Path tmp = outDir.resolve("_tmp");
        if (Files.isDirectory(tmp)) {
            Files.walk(tmp).sorted(Comparator.reverseOrder()).map(Path::toFile).forEach(File::delete);
        }

        System.out.printf("Results → %s%n", outDir.resolve("results.txt"));
    }

    static String resolveBin() {
        String env = System.getenv("TP4_BIN_PATH");
        if (env != null && !env.isEmpty()) return env + "/benchmark";
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp4-bin/benchmark").toAbsolutePath().normalize().toString();
    }
}
