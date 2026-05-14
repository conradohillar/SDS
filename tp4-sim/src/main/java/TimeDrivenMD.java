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
 * Neighbor search: brute-force O(N²) by default; Cell Index Method (O(N))
 *   enabled with --cim. Cell size = SIGMA_PP = 2 m, grid 40×40.
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
 *   --cim                 use Cell Index Method for neighbor search
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

    // ── Cell Index Method constants ───────────────────────────────────────────
    // Cell size equals interaction cutoff → only adjacent cells need checking.
    static final double CELL_SIZE  = SIGMA_PP;                         // 2 m
    static final int    GRID_M     = (int)(2 * R_DOMAIN / CELL_SIZE);  // 40
    static final int    GRID_TOTAL = GRID_M * GRID_M;                  // 1600
    // Forward half-shell: covers all 9 neighbors, each unordered pair once.
    static final int[][] NEIGHBOR_OFFSETS = {{0,0},{0,1},{1,-1},{1,0},{1,1}};

    static final int FRESH = 0;
    static final int USED  = 1;

    // ── Instance state ────────────────────────────────────────────────────────
    int    n;
    double k;
    double[] x, y, vx, vy, fx, fy;
    int[]    state;
    boolean[] obsContact, wallContact;
    long cfc = 0;
    Random rng;

    // ── CIM linked-list state (allocated only when useCim=true) ───────────────
    final boolean useCim;
    int[] cellHead;  // [GRID_TOTAL] head particle index per cell, -1 = empty
    int[] cellNext;  // [n]          next particle in same cell,   -1 = end

    // ── Constructor ───────────────────────────────────────────────────────────
    TimeDrivenMD(int n, double k, long seed, boolean useCim) {
        this.n      = n;
        this.k      = k;
        this.useCim = useCim;
        this.x  = new double[n]; this.y  = new double[n];
        this.vx = new double[n]; this.vy = new double[n];
        this.fx = new double[n]; this.fy = new double[n];
        this.state       = new int[n];
        this.obsContact  = new boolean[n];
        this.wallContact = new boolean[n];
        this.rng = new Random(seed);
        if (useCim) {
            cellHead = new int[GRID_TOTAL];
            cellNext = new int[n];
        }
        placeParticles();
        computeForces();
    }

    static class Point {
        double x, y;
        Point(double x, double y) { this.x = x; this.y = y; }
    }

    void placeParticles() {
        double step = SIGMA_PP + 0.001;
        List<Point> validPositions = new ArrayList<>();

        double rMax = R_WALL_EFF - 0.01;
        double rMin = SIGMA_OBS + 0.01;

        double dx = step;
        double dy = step * Math.sqrt(3.0) / 2.0;

        int iMax = (int) Math.ceil(rMax / dy);
        int jMax = (int) Math.ceil(rMax / dx);

        for (int i = -iMax; i <= iMax; i++) {
            double yi = i * dy;
            double xOffset = (Math.abs(i) % 2 == 1) ? (dx / 2.0) : 0.0;
            for (int j = -jMax - 1; j <= jMax; j++) {
                double xi = j * dx + xOffset;
                double r = Math.sqrt(xi * xi + yi * yi);
                if (r >= rMin && r <= rMax)
                    validPositions.add(new Point(xi, yi));
            }
        }

        if (validPositions.size() < n)
            throw new RuntimeException(String.format(
                "Cannot place %d particles. Grid capacity is %d", n, validPositions.size()));

        Collections.shuffle(validPositions, rng);

        for (int i = 0; i < n; i++) {
            Point p = validPositions.get(i);
            x[i] = p.x;
            y[i] = p.y;
            double speed  = 1.0;  // v0 = 1 m/s as per rubric
            double vAngle = rng.nextDouble() * 2 * Math.PI;
            vx[i] = speed * Math.cos(vAngle);
            vy[i] = speed * Math.sin(vAngle);
            state[i] = FRESH;
        }
    }

    // ── Force computation ─────────────────────────────────────────────────────
    void computeForces() {
        if (useCim) computeForcesCIM();
        else        computeForcesBrute();
    }

    void computeForcesBrute() {
        Arrays.fill(fx, 0.0);
        Arrays.fill(fy, 0.0);

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

        applyBoundaryForces();
    }

    void computeForcesCIM() {
        Arrays.fill(fx, 0.0);
        Arrays.fill(fy, 0.0);

        buildCellList();

        for (int ci = 0; ci < GRID_TOTAL; ci++) {
            if (cellHead[ci] == -1) continue;
            int rowA = ci / GRID_M, colA = ci % GRID_M;

            for (int[] off : NEIGHBOR_OFFSETS) {
                int rowB = rowA + off[0], colB = colA + off[1];
                if (rowB < 0 || rowB >= GRID_M || colB < 0 || colB >= GRID_M) continue;
                int cj = rowB * GRID_M + colB;
                if (cellHead[cj] == -1) continue;

                for (int i = cellHead[ci]; i != -1; i = cellNext[i]) {
                    // same cell: start j after i to avoid double-counting
                    int jStart = (ci == cj) ? cellNext[i] : cellHead[cj];
                    for (int j = jStart; j != -1; j = cellNext[j]) {
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
            }
        }

        applyBoundaryForces();
    }

    void buildCellList() {
        Arrays.fill(cellHead, -1);
        for (int i = 0; i < n; i++) {
            int col = Math.min(GRID_M - 1, Math.max(0, (int)((x[i] + R_DOMAIN) / CELL_SIZE)));
            int row = Math.min(GRID_M - 1, Math.max(0, (int)((y[i] + R_DOMAIN) / CELL_SIZE)));
            int ci = row * GRID_M + col;
            cellNext[i] = cellHead[ci];
            cellHead[ci] = i;
        }
    }

    void applyBoundaryForces() {
        // particle-obstacle (center at origin, repulsive outward)
        for (int i = 0; i < n; i++) {
            double dist2 = x[i] * x[i] + y[i] * y[i];
            if (dist2 < SIGMA_OBS * SIGMA_OBS && dist2 > 1e-20) {
                double dist = Math.sqrt(dist2);
                double xi   = SIGMA_OBS - dist;
                double fMag = k * xi / dist;
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

        computeForces();

        for (int i = 0; i < n; i++) {
            vx[i] += (fx[i] / MASS) * halfDt;
            vy[i] += (fy[i] / MASS) * halfDt;
        }

        updateStates();
    }

    void updateStates() {
        for (int i = 0; i < n; i++) {
            double r = Math.sqrt(x[i] * x[i] + y[i] * y[i]);

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
            } else {
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
        for (int i = 0; i < n; i++)
            ekin += 0.5 * MASS * (vx[i] * vx[i] + vy[i] * vy[i]);

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
        for (int i = 0; i < n; i++) {
            double dist = Math.sqrt(x[i] * x[i] + y[i] * y[i]);
            if (dist < SIGMA_OBS) {
                double xi = SIGMA_OBS - dist;
                epot += 0.5 * k * xi * xi;
            }
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
        for (int i = 0; i < n; i++)
            w.printf("%.6f %.6f %.6f %.6f %d%n", x[i], y[i], vx[i], vy[i], state[i]);
    }

    // ── Main simulation loop ──────────────────────────────────────────────────
    static void run(int n, long seed, double dt, double tf, double dt2,
                    double k, int maxFrames, boolean noFrames, boolean noStats,
                    boolean useCim, Path outDir) throws IOException {

        Files.createDirectories(outDir);
        Path framesDir = outDir.resolve("frames");
        if (!noFrames) Files.createDirectories(framesDir);

        TimeDrivenMD sim = new TimeDrivenMD(n, k, seed, useCim);

        PrintWriter wStats  = noStats ? null : open(outDir.resolve("stats.txt"));
        PrintWriter wEnergy = noStats ? null : open(outDir.resolve("energy.txt"));
        PrintWriter wCfc    = open(outDir.resolve("cfc.txt"));

        if (wStats  != null) wStats.println("t Cfc nUsed");
        if (wEnergy != null) wEnergy.println("t Ekin Epot Etot");

        int frameIdx       = 0;
        int totalSteps     = (int) Math.ceil(tf / dt);
        int stepsPerOutput = Math.max(1, (int) Math.round(dt2 / dt));
        long prevCfc       = 0;

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

            if (sim.cfc > prevCfc) {
                for (long ev = prevCfc + 1; ev <= sim.cfc; ev++)
                    wCfc.printf("%.8f%n", t);
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

        try (var wM = open(outDir.resolve("metadata.txt"))) {
            wM.printf("N %d%n", n);
            wM.printf("seed %d%n", seed);
            wM.printf("dt %.6e%n", dt);
            wM.printf("dt2 %.6e%n", dt2);
            wM.printf("tf %.4f%n", tf);
            wM.printf("k %.4f%n", k);
            wM.printf("cim %b%n", useCim);
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

    static String resolveBin() {
        String env = System.getenv("TP4_BIN_PATH");
        if (env != null && !env.isEmpty()) return env;
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp4-bin").toAbsolutePath().normalize().toString();
    }

    // ── Entry point ───────────────────────────────────────────────────────────
    public static void main(String[] args) throws IOException {
        int     n        = 200;
        long    seed     = 42L;
        double  dt       = 0.01;
        double  tf       = 1000.0;
        double  dt2      = 10.0;
        double  kConst   = 1000.0;
        int     maxFrames = 0;
        boolean noFrames  = false;
        boolean noStats   = false;
        boolean useCim    = false;
        String  binPath   = resolveBin();
        String  runId     = "default";

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
                case "--cim"        -> useCim    = true;
                case "--bin"        -> binPath   = args[++i];
                case "--run-id"     -> runId     = args[++i];
            }
        }

        Path outDir = Paths.get(binPath).resolve(runId);
        System.out.printf("TimeDrivenMD  N=%d  seed=%d  dt=%.2e  tf=%.1f  k=%.1f  cim=%b%n",
                n, seed, dt, tf, kConst, useCim);
        System.out.printf("Output → %s%n", outDir);

        long t0 = System.currentTimeMillis();
        run(n, seed, dt, tf, dt2, kConst, maxFrames, noFrames, noStats, useCim, outDir);
        double elapsed = (System.currentTimeMillis() - t0) / 1000.0;
        System.out.printf("Done in %.2f s%n", elapsed);
    }
}
