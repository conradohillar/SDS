import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * TP4 Sistema 2 – Time-Driven Molecular Dynamics (Velocity Verlet).
 *
 * Domain: circular, R_DOMAIN=40 m, R_OBSTACLE=1 m, R_PARTICLE=1 m.
 * Forces: elastic repulsion F = k*xi*(xi-xj)/|xi-xj|, xi = sigma - |dr|
 *   particle-particle: sigma_pp = 2*R_PARTICLE = 2 m
 *   particle-obstacle: sigma_obs = R_OBSTACLE + R_PARTICLE = 2 m (repulsive outward)
 *   particle-wall:     sigma_wall = R_DOMAIN - R_PARTICLE = 39 m (repulsive inward)
 *
 * State machine (same logic as TP3):
 *   FRESH (0) → touches obstacle → USED (1) → touches wall → FRESH (0)
 *   Each fresh→obstacle transition increments Cfc (cumulative flow count).
 *
 * Integrator: Velocity Verlet.
 *
 * Output (written every dt2 seconds):
 *   frames/frame_NNNNNN.txt  – t, then N lines of "x y vx vy state"
 *   stats.txt                – t Cfc nUsed
 *   energy.txt               – t Ekin Epot Etot
 *   cfc.txt                  – timestamps of each Cfc increment (one per line)
 *   metadata.txt             – key-value pairs
 *
 * CLI:
 *   --n         <int>     number of particles (default 200)
 *   --seed      <long>    RNG seed (default 42)
 *   --tf        <double>  final time [s] (default 1000)
 *   --dt        <double>  integration step [s] (default 0.01)
 *   --dt2       <double>  output step [s] (default 10.0)
 *   --k         <double>  elastic constant [N/m] (default 1000.0)
 *   --max-frames <int>    maximum frame files to write (0=unlimited, default 0)
 *   --no-frames           skip writing frame files
 *   --no-stats            skip writing stats/energy files
 *   --bin       <path>    output base dir (default ../tp4-bin)
 *   --run-id    <string>  sub-directory name for this run (default "default")
 */
public class TimeDrivenMD {

    // ── Domain constants ──────────────────────────────────────────────────────
    static final double R_DOMAIN   = 40.0;
    static final double R_OBSTACLE = 1.0;
    static final double R_PARTICLE = 1.0;
    static final double SIGMA_PP   = 2.0 * R_PARTICLE;          // 2 m
    static final double SIGMA_OBS  = R_OBSTACLE + R_PARTICLE;   // 2 m
    static final double R_WALL_EFF = R_DOMAIN - R_PARTICLE;     // 39 m
    static final double MASS       = 1.0;

    static final int FRESH = 0;
    static final int USED  = 1;

    // ── State ─────────────────────────────────────────────────────────────────
    int    n;
    double k;
    double[] x, y, vx, vy, fx, fy;
    int[]    state;
    boolean[] obsContact, wallContact;

    long cfc = 0;

    Random rng;

    // ── Constructor + initialisation ──────────────────────────────────────────
    TimeDrivenMD(int n, double k, long seed) {
        this.n = n;
        this.k = k;
        this.x  = new double[n]; this.y  = new double[n];
        this.vx = new double[n]; this.vy = new double[n];
        this.fx = new double[n]; this.fy = new double[n];
        this.state = new int[n];
        this.obsContact  = new boolean[n];
        this.wallContact = new boolean[n];
        this.rng = new Random(seed);
        placeParticles();
        computeForces();
    }

    void placeParticles() {
        int placed = 0;
        int attempts = 0;
        while (placed < n) {
            if (++attempts > 1_000_000) throw new RuntimeException("Cannot place all particles");
            double angle = rng.nextDouble() * 2 * Math.PI;
            double rMax  = R_WALL_EFF - 0.01;
            double rMin  = SIGMA_OBS + 0.01;
            double rSq   = rMin * rMin + rng.nextDouble() * (rMax * rMax - rMin * rMin);
            double r     = Math.sqrt(rSq);
            double xi    = r * Math.cos(angle);
            double yi    = r * Math.sin(angle);

            boolean ok = true;
            for (int j = 0; j < placed; j++) {
                double dx = xi - x[j], dy = yi - y[j];
                if (dx * dx + dy * dy < SIGMA_PP * SIGMA_PP) { ok = false; break; }
            }
            if (ok) {
                x[placed] = xi; y[placed] = yi;
                // random velocity direction, speed ~ sqrt(k/m)*sigma/10 ≈ small
                double speed = 0.1 * Math.sqrt(k / MASS) * R_PARTICLE;
                double vAngle = rng.nextDouble() * 2 * Math.PI;
                vx[placed] = speed * Math.cos(vAngle);
                vy[placed] = speed * Math.sin(vAngle);
                state[placed] = FRESH;
                placed++;
            }
        }
    }

    // ── Force computation ─────────────────────────────────────────────────────
    void computeForces() {
        Arrays.fill(fx, 0.0);
        Arrays.fill(fy, 0.0);

        // particle-particle
        for (int i = 0; i < n - 1; i++) {
            for (int j = i + 1; j < n; j++) {
                double dx = x[i] - x[j], dy = y[i] - y[j];
                double dist2 = dx * dx + dy * dy;
                if (dist2 < SIGMA_PP * SIGMA_PP && dist2 > 1e-20) {
                    double dist = Math.sqrt(dist2);
                    double xi   = SIGMA_PP - dist;
                    double fMag = k * xi / dist;
                    fx[i] += fMag * dx;  fy[i] += fMag * dy;
                    fx[j] -= fMag * dx;  fy[j] -= fMag * dy;
                }
            }
        }

        // particle-obstacle (center at origin, repulsive outward)
        for (int i = 0; i < n; i++) {
            double dist2 = x[i] * x[i] + y[i] * y[i];
            if (dist2 < SIGMA_OBS * SIGMA_OBS && dist2 > 1e-20) {
                double dist = Math.sqrt(dist2);
                double xi   = SIGMA_OBS - dist;
                double fMag = k * xi / dist;
                // push particle away from obstacle (outward direction = x[i]/dist)
                fx[i] += fMag * x[i];
                fy[i] += fMag * y[i];
            }
        }

        // particle-wall (repulsive inward: toward center)
        for (int i = 0; i < n; i++) {
            double dist2 = x[i] * x[i] + y[i] * y[i];
            double dist  = Math.sqrt(dist2);
            if (dist > R_WALL_EFF) {
                double xi   = dist - R_WALL_EFF;
                double fMag = k * xi / dist;
                // push inward (toward center)
                fx[i] -= fMag * x[i];
                fy[i] -= fMag * y[i];
            }
        }
    }

    // ── Velocity Verlet step ──────────────────────────────────────────────────
    void step(double dt) {
        double halfDt = 0.5 * dt;
        double dtSq   = dt * dt;

        for (int i = 0; i < n; i++) {
            double ax = fx[i] / MASS, ay = fy[i] / MASS;
            x[i]  += vx[i] * dt + ax * dtSq * 0.5;
            y[i]  += vy[i] * dt + ay * dtSq * 0.5;
            vx[i] += ax * halfDt;
            vy[i] += ay * halfDt;
        }

        double[] fxOld = fx.clone();
        double[] fyOld = fy.clone();

        computeForces();

        for (int i = 0; i < n; i++) {
            vx[i] += (fx[i] / MASS) * halfDt;
            vy[i] += (fy[i] / MASS) * halfDt;
        }

        // update contact flags and state machine
        updateStates();
    }

    void updateStates() {
        for (int i = 0; i < n; i++) {
            double r2 = x[i] * x[i] + y[i] * y[i];
            double r  = Math.sqrt(r2);

            if (state[i] == FRESH) {
                boolean touching = r <= SIGMA_OBS;
                if (touching && !obsContact[i]) {
                    state[i] = USED;
                    obsContact[i]  = true;
                    wallContact[i] = false;
                    cfc++;
                } else if (!touching) {
                    obsContact[i] = false;
                }
            } else { // USED
                boolean touchingWall = r >= R_WALL_EFF;
                if (touchingWall && !wallContact[i]) {
                    state[i] = FRESH;
                    wallContact[i] = true;
                    obsContact[i]  = false;
                } else if (!touchingWall) {
                    wallContact[i] = false;
                }
            }
        }
    }

    // ── Energy ────────────────────────────────────────────────────────────────
    double[] computeEnergy() {
        double ekin = 0, epot = 0;
        for (int i = 0; i < n; i++) {
            ekin += 0.5 * MASS * (vx[i] * vx[i] + vy[i] * vy[i]);
        }
        // particle-particle potential
        for (int i = 0; i < n - 1; i++) {
            for (int j = i + 1; j < n; j++) {
                double dx = x[i] - x[j], dy = y[i] - y[j];
                double dist2 = dx * dx + dy * dy;
                if (dist2 < SIGMA_PP * SIGMA_PP) {
                    double xi = SIGMA_PP - Math.sqrt(dist2);
                    epot += 0.5 * k * xi * xi;
                }
            }
        }
        // obstacle potential
        for (int i = 0; i < n; i++) {
            double dist = Math.sqrt(x[i] * x[i] + y[i] * y[i]);
            if (dist < SIGMA_OBS) {
                double xi = SIGMA_OBS - dist;
                epot += 0.5 * k * xi * xi;
            }
        }
        // wall potential
        for (int i = 0; i < n; i++) {
            double dist = Math.sqrt(x[i] * x[i] + y[i] * y[i]);
            if (dist > R_WALL_EFF) {
                double xi = dist - R_WALL_EFF;
                epot += 0.5 * k * xi * xi;
            }
        }
        return new double[]{ekin, epot, ekin + epot};
    }

    // ── I/O helpers ───────────────────────────────────────────────────────────
    static PrintWriter open(Path p) throws IOException {
        Files.createDirectories(p.getParent());
        return new PrintWriter(Files.newBufferedWriter(p));
    }

    void writeFrame(PrintWriter w, double t) {
        w.printf("%.6f%n", t);
        for (int i = 0; i < n; i++) {
            w.printf("%.6f %.6f %.6f %.6f %d%n", x[i], y[i], vx[i], vy[i], state[i]);
        }
    }

    // ── Main simulation loop ──────────────────────────────────────────────────
    static void run(int n, long seed, double dt, double tf, double dt2,
                    double k, int maxFrames, boolean noFrames, boolean noStats,
                    Path outDir) throws IOException {

        Files.createDirectories(outDir);
        Path framesDir = outDir.resolve("frames");
        if (!noFrames) Files.createDirectories(framesDir);

        TimeDrivenMD sim = new TimeDrivenMD(n, k, seed);

        PrintWriter wStats  = noStats ? null : open(outDir.resolve("stats.txt"));
        PrintWriter wEnergy = noStats ? null : open(outDir.resolve("energy.txt"));
        PrintWriter wCfc    = open(outDir.resolve("cfc.txt"));

        if (wStats  != null) wStats.println("t Cfc nUsed");
        if (wEnergy != null) wEnergy.println("t Ekin Epot Etot");

        int frameIdx  = 0;
        int stepCount = 0;
        int totalSteps = (int) Math.ceil(tf / dt);
        int stepsPerOutput = Math.max(1, (int) Math.round(dt2 / dt));

        long prevCfc = 0;

        // write initial state
        if (!noFrames && (maxFrames == 0 || frameIdx < maxFrames)) {
            try (var wF = open(framesDir.resolve(String.format("frame_%06d.txt", frameIdx)))) {
                sim.writeFrame(wF, 0.0);
            }
            frameIdx++;
        }
        if (wStats  != null) wStats.printf("%.6f %d %d%n", 0.0, sim.cfc, countUsed(sim));
        if (wEnergy != null) { double[] e = sim.computeEnergy(); wEnergy.printf("%.6f %.6f %.6f %.6f%n", 0.0, e[0], e[1], e[2]); }

        for (int s = 1; s <= totalSteps; s++) {
            double t = s * dt;
            sim.step(dt);

            // record cfc events
            if (sim.cfc > prevCfc) {
                for (long ev = prevCfc + 1; ev <= sim.cfc; ev++) {
                    wCfc.printf("%.8f%n", t);
                }
                prevCfc = sim.cfc;
            }

            if (s % stepsPerOutput == 0) {
                if (!noFrames && (maxFrames == 0 || frameIdx < maxFrames)) {
                    try (var wF = open(framesDir.resolve(String.format("frame_%06d.txt", frameIdx)))) {
                        sim.writeFrame(wF, t);
                    }
                    frameIdx++;
                }
                if (wStats  != null) wStats.printf("%.6f %d %d%n", t, sim.cfc, countUsed(sim));
                if (wEnergy != null) { double[] e = sim.computeEnergy(); wEnergy.printf("%.6f %.6f %.6f %.6f%n", t, e[0], e[1], e[2]); }
            }
        }

        wCfc.close();
        if (wStats  != null) wStats.close();
        if (wEnergy != null) wEnergy.close();

        // write metadata
        try (var wM = open(outDir.resolve("metadata.txt"))) {
            wM.printf("N %d%n", n);
            wM.printf("seed %d%n", seed);
            wM.printf("dt %.6e%n", dt);
            wM.printf("dt2 %.6e%n", dt2);
            wM.printf("tf %.4f%n", tf);
            wM.printf("k %.4f%n", k);
            wM.printf("R_DOMAIN %.4f%n", R_DOMAIN);
            wM.printf("R_OBSTACLE %.4f%n", R_OBSTACLE);
            wM.printf("R_PARTICLE %.4f%n", R_PARTICLE);
            wM.printf("Cfc %d%n", sim.cfc);
        }
    }

    static int countUsed(TimeDrivenMD sim) {
        int c = 0;
        for (int s : sim.state) if (s == USED) c++;
        return c;
    }

    // ── Resolve default bin dir ────────────────────────────────────────────────
    static String resolveBin() {
        String env = System.getenv("TP4_BIN_PATH");
        if (env != null && !env.isEmpty()) return env;
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp4-bin").toAbsolutePath().normalize().toString();
    }

    // ── Entry point ───────────────────────────────────────────────────────────
    public static void main(String[] args) throws IOException {
        int    n         = 200;
        long   seed      = 42L;
        double dt        = 0.01;
        double tf        = 1000.0;
        double dt2       = 10.0;
        double kConst    = 1000.0;
        int    maxFrames = 0;
        boolean noFrames = false;
        boolean noStats  = false;
        String binPath   = resolveBin();
        String runId     = "default";

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--n"          -> n         = Integer.parseInt(args[++i]);
                case "--seed"       -> seed      = Long.parseLong(args[++i]);
                case "--dt"         -> dt        = Double.parseDouble(args[++i]);
                case "--tf"         -> tf        = Double.parseDouble(args[++i]);
                case "--dt2"        -> dt2       = Double.parseDouble(args[++i]);
                case "--k"          -> kConst    = Double.parseDouble(args[++i]);
                case "--max-frames" -> maxFrames = Integer.parseInt(args[++i]);
                case "--no-frames"  -> noFrames  = true;
                case "--no-stats"   -> noStats   = true;
                case "--bin"        -> binPath   = args[++i];
                case "--run-id"     -> runId     = args[++i];
            }
        }

        Path outDir = Paths.get(binPath).resolve(runId);
        System.out.printf("TimeDrivenMD  N=%d  seed=%d  dt=%.2e  tf=%.1f  k=%.1f%n",
                n, seed, dt, tf, kConst);
        System.out.printf("Output → %s%n", outDir);

        long t0 = System.currentTimeMillis();
        run(n, seed, dt, tf, dt2, kConst, maxFrames, noFrames, noStats, outDir);
        double elapsed = (System.currentTimeMillis() - t0) / 1000.0;
        System.out.printf("Done in %.2f s%n", elapsed);
    }
}
