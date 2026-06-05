import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * TP5 Active Matter Runner – launches all (mode × N × realization) tasks in parallel.
 *
 * Output structure: <bin>/runs/<mode>/N<n>/r<r>/
 *
 * CLI:
 *   --tf        <double>  simulation time (default 10000)
 *   --dt        <double>  integration step (default 0.01)
 *   --dt2       <double>  output interval (default 0.1)
 *   --runs      <int>     realizations per (mode, N) (default 5)
 *   --no-frames           skip frame files (saves disk, analysis still works via stats.txt)
 *   --bin       <path>    output base dir (default ../tp5-bin)
 */
public class ActiveRunner {

    static final String[] ALL_MODES        = {"quiral", "random"};
    static final int[]    DEFAULT_N_VALUES = {20, 21, 22, 23, 24, 25, 26, 27};

    public static void main(String[] args) throws Exception {
        double  tf       = 10000.0;
        double  dt       = 0.01;
        double  dt2      = 0.1;
        int     runs     = 5;
        boolean noFrames = false;
        String  bin      = TimeDrivenActive.resolveBin();
        List<String> modeList = new ArrayList<>(Arrays.asList(ALL_MODES));
        int[] nValues = DEFAULT_N_VALUES;

        for (int i=0; i<args.length; i++) switch (args[i]) {
            case "--tf"        -> tf       = Double.parseDouble(args[++i]);
            case "--dt"        -> dt       = Double.parseDouble(args[++i]);
            case "--dt2"       -> dt2      = Double.parseDouble(args[++i]);
            case "--runs"      -> runs     = Integer.parseInt(args[++i]);
            case "--no-frames" -> noFrames = true;
            case "--bin"       -> bin      = args[++i];
            case "--modes"     -> { modeList.clear();
                                    for (String m : args[++i].split(",")) modeList.add(m.trim()); }
            case "--n-values"  -> { String[] tok = args[++i].split(",");
                                    nValues = new int[tok.length];
                                    for (int k=0;k<tok.length;k++) nValues[k] = Integer.parseInt(tok[k].trim()); }
            case "--r-p"       -> TimeDrivenActive.R_P       = Double.parseDouble(args[++i]);
            case "--r-domain"  -> TimeDrivenActive.R_DOMAIN  = Double.parseDouble(args[++i]);
            case "--v0"        -> TimeDrivenActive.V0        = Double.parseDouble(args[++i]);
            case "--kappa"     -> TimeDrivenActive.KAPPA     = Double.parseDouble(args[++i]);
            case "--sigma-eta" -> TimeDrivenActive.SIGMA_ETA = Double.parseDouble(args[++i]);
        }
        TimeDrivenActive.refreshDerived();
        String[] MODES = modeList.toArray(new String[0]);
        final int[] N_VALUES = nValues;

        int nThreads = Runtime.getRuntime().availableProcessors();
        ExecutorService pool = Executors.newFixedThreadPool(nThreads);
        List<Future<?>> futures = new ArrayList<>();

        int totalTasks = MODES.length * N_VALUES.length * runs;
        System.out.printf("ActiveRunner: modes=%s N=%s runs=%d threads=%d%n",
            Arrays.toString(MODES), Arrays.toString(N_VALUES), runs, nThreads);
        System.out.printf("Physical: r_p=%.3f R=%.3f v0=%.3f kappa=%.2f sigma_eta=%.3f%n",
            TimeDrivenActive.R_P, TimeDrivenActive.R_DOMAIN, TimeDrivenActive.V0,
            TimeDrivenActive.KAPPA, TimeDrivenActive.SIGMA_ETA);
        System.out.printf("Total tasks: %d%n", totalTasks);

        final double tfF=tf, dtF=dt, dt2F=dt2;
        final boolean noFr = noFrames;
        final String binF  = bin;

        for (String mode : MODES) {
            for (int n : N_VALUES) {
                for (int r=0; r<runs; r++) {
                    final String mF = mode;
                    final int    nF = n, rF = r;
                    futures.add(pool.submit(() -> {
                        Path outDir = Paths.get(binF, "runs", mF, "N"+nF, "r"+rF);
                        try {
                            if (Files.exists(outDir.resolve("stats.txt"))) {
                                System.out.printf("  SKIP  %-7s N=%2d r=%d (exists)%n", mF, nF, rF);
                                return null;
                            }
                            System.out.printf("  START %-7s N=%2d r=%d%n", mF, nF, rF);
                            long seed = ThreadLocalRandom.current().nextLong();
                            TimeDrivenActive.run(nF, seed, mF, dtF, tfF, dt2F, noFr, outDir);
                            System.out.printf("  DONE  %-7s N=%2d r=%d%n", mF, nF, rF);
                        } catch (Exception e) {
                            System.err.printf("  ERROR %-7s N=%2d r=%d: %s%n",
                                mF, nF, rF, e.getMessage());
                            e.printStackTrace(System.err);
                        }
                        return null;
                    }));
                }
            }
        }

        pool.shutdown();
        for (Future<?> f : futures) f.get();
        System.out.println("All tasks complete → " + binF + "/runs/");
    }
}
