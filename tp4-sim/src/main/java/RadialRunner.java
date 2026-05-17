import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * TP4 Radial Profile Runner – launches one thread per (N, realization) pair
 * for each k value, writing frames for radial profile analysis.
 *
 * Output structure: <bin>/radial/k<k>/N<n>/r<r>/frames/...
 *
 * CLI:
 *   --tf    <double>  simulation time (default 3000)
 *   --dt    <double>  integration step (default 0.001)
 *   --dt2   <double>  output interval (default 0.1)
 *   --runs  <int>     realizations per (k,N) pair (default 5)
 *   --bin   <path>    output base dir (default ../tp4-bin)
 */
public class RadialRunner {

    static final double[] K_VALUES = {100.0, 1000.0, 10000.0, 100000.0};
    static final int[]    N_VALUES = {100, 200, 300, 400, 500, 600, 700, 800, 900, 1000};

    public static void main(String[] args) throws Exception {
        double tf   = 3000.0;
        double dt   = 0.001;
        double dt2  = 0.1;
        int    runs = 5;
        String bin  = resolveBin();

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--tf"   -> tf   = Double.parseDouble(args[++i]);
                case "--dt"   -> dt   = Double.parseDouble(args[++i]);
                case "--dt2"  -> dt2  = Double.parseDouble(args[++i]);
                case "--runs" -> runs = Integer.parseInt(args[++i]);
                case "--bin"  -> bin  = args[++i];
            }
        }

        int nThreads = Runtime.getRuntime().availableProcessors();
        ExecutorService pool = Executors.newFixedThreadPool(nThreads);
        List<Future<?>> futures = new ArrayList<>();

        System.out.printf("RadialRunner: tf=%.0f dt=%.1e dt2=%.2f runs=%d threads=%d%n",
                tf, dt, dt2, runs, nThreads);
        System.out.printf("k values: %s%n", Arrays.toString(K_VALUES));
        System.out.printf("N values: %s%n", Arrays.toString(N_VALUES));
        System.out.printf("Total tasks: %d%n", K_VALUES.length * N_VALUES.length * runs);

        final double tfF = tf, dtF = dt, dt2F = dt2;
        final String binF = bin;

        for (double k : K_VALUES) {
            String kTag = String.format("k%.0f", k);
            for (int n : N_VALUES) {
                for (int r = 0; r < runs; r++) {
                    final double kk = k;
                    final int nn = n, rr = r;
                    final String kTagF = kTag;
                    futures.add(pool.submit(() -> {
                        Path outDir = Paths.get(binF, "radial", kTagF, "N" + nn, "r" + rr);
                        try {
                            System.out.printf("  START k=%.0f N=%4d r=%d%n", kk, nn, rr);
                            TimeDrivenMD.run(nn, rr, dtF, tfF, dt2F,
                                    kk, 0, false, false, true, outDir);
                            System.out.printf("  DONE  k=%.0f N=%4d r=%d%n", kk, nn, rr);
                        } catch (Exception e) {
                            System.err.printf("  ERROR k=%.0f N=%d r=%d: %s%n",
                                    kk, nn, rr, e.getMessage());
                            e.printStackTrace(System.err);
                        }
                        return null;
                    }));
                }
            }
        }

        pool.shutdown();
        for (Future<?> f : futures) f.get();
        System.out.println("All tasks complete → " + binF + "/radial/");
    }

    static String resolveBin() {
        String env = System.getenv("TP4_BIN_PATH");
        if (env != null && !env.isEmpty()) return env;
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp4-bin").toAbsolutePath().normalize().toString();
    }
}
