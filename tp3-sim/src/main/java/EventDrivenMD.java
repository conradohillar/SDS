import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * Event-Driven Molecular Dynamics – Sistema 1 TP3.
 *
 * Domain: circular enclosure of radius R_DOMAIN = 40 m (L = 80 m diameter).
 * Fixed obstacle: circle of radius R_OBSTACLE = 1 m at the origin.
 * Mobile particles: radius R_PARTICLE = 1 m, speed V0 = 1 m/s, mass m = 1 kg.
 *
 * State machine:
 *   FRESH (0, green)  --[hits obstacle]--> USED (1, purple)
 *   USED  (1, purple) --[hits outer wall]--> FRESH (0, green)
 *
 * Output (written to --bin directory):
 *   frames/frame_NNNNN.txt  – one frame per K events (format: t; N lines of x y vx vy state)
 *   stats.txt               – one row per event: time Cfc Nu
 *   metadata.txt            – simulation parameters
 *
 * CLI flags:
 *   --n          <int>    number of particles          (default 50)
 *   --seed       <long>   random seed                  (default 42)
 *   --tf         <double> simulation end time [s]      (default 100)
 *   --max-frames <int>    frame cap (0 = no frames)    (default 2000)
 *   --frame-every<int>    write frame every N events   (default 10)
 *   --no-stats            skip writing stats.txt
 *   --bin        <path>   output directory             (default ../tp3-bin)
 */
public class EventDrivenMD {

    // ── Physical constants ─────────────────────────────────────────────────────
    static final double R_DOMAIN   = 40.0;  // outer wall radius [m]
    static final double R_OBSTACLE = 1.0;   // fixed obstacle radius [m]
    static final double R_PARTICLE = 1.0;   // mobile particle radius [m]
    static final double V0         = 1.0;   // particle speed [m/s]

    // Derived
    static final double SIGMA_PP   = 2 * R_PARTICLE;            // 2.0 – particle-particle contact
    static final double SIGMA_OBS  = R_OBSTACLE + R_PARTICLE;   // 2.0 – particle-obstacle contact
    static final double R_WALL_EFF = R_DOMAIN - R_PARTICLE;     // 39.0 – effective wall radius

    static final int FRESH = 0, USED = 1;
    static final int EVT_PP = 0, EVT_OBS = 1, EVT_WALL = 2;
    static final double INF = Double.POSITIVE_INFINITY;
    static final double EPS = 1e-10; // minimum positive collision time

    // ── Event ─────────────────────────────────────────────────────────────────
    record Event(double time, int type, int i, int j, int ci, int cj)
            implements Comparable<Event> {
        @Override
        public int compareTo(Event o) { return Double.compare(time, o.time); }
    }

    // ── Simulation state ──────────────────────────────────────────────────────
    final int N;
    final double[] x, y, vx, vy;
    final int[]    state, cc;   // cc[i] = collision count of particle i (invalidation key)
    double currentTime = 0.0;
    long   Cfc = 0;             // cumulative fresh→center transitions

    final PriorityQueue<Event> pq = new PriorityQueue<>();

    // ── Constructor ───────────────────────────────────────────────────────────
    EventDrivenMD(int n, long seed) {
        this.N = n;
        x = new double[n]; y = new double[n];
        vx = new double[n]; vy = new double[n];
        state = new int[n]; cc = new int[n];
        placeParticles(new Random(seed));
        scheduleAll();
    }

    // ── Placement ─────────────────────────────────────────────────────────────
    void placeParticles(Random rng) {
        for (int i = 0; i < N; i++) {
            int attempts = 0;
            while (true) {
                double theta = rng.nextDouble() * 2 * Math.PI;
                double r = SIGMA_OBS + rng.nextDouble() * (R_WALL_EFF - SIGMA_OBS);
                double px = r * Math.cos(theta);
                double py = r * Math.sin(theta);
                boolean ok = true;
                for (int j = 0; j < i; j++) {
                    double dx = px - x[j], dy = py - y[j];
                    if (dx * dx + dy * dy < SIGMA_PP * SIGMA_PP) { ok = false; break; }
                }
                if (ok) {
                    x[i] = px; y[i] = py;
                    double phi = rng.nextDouble() * 2 * Math.PI;
                    vx[i] = V0 * Math.cos(phi); vy[i] = V0 * Math.sin(phi);
                    state[i] = FRESH;
                    break;
                }
                if (++attempts > 300_000)
                    throw new RuntimeException(
                        "Cannot place particle " + i + " without overlap (N=" + N + ")");
            }
        }
    }

    // ── Collision time predictors ──────────────────────────────────────────────

    /**
     * Time until particles i and j collide.
     * Uses the quadratic formula: |Δr + Δv·t|² = σ²
     */
    double tcPP(int i, int j) {
        double dx  = x[i] - x[j],  dy  = y[i] - y[j];
        double dvx = vx[i] - vx[j], dvy = vy[i] - vy[j];
        double dvdr = dx * dvx + dy * dvy;
        if (dvdr >= 0) return INF;                    // diverging
        double dv2 = dvx * dvx + dvy * dvy;
        if (dv2 == 0) return INF;
        double dr2 = dx * dx + dy * dy;
        double d   = dvdr * dvdr - dv2 * (dr2 - SIGMA_PP * SIGMA_PP);
        if (d < 0) return INF;                        // miss
        double dt = -(dvdr + Math.sqrt(d)) / dv2;
        return dt > EPS ? dt : INF;
    }

    /**
     * Time until particle i hits the central fixed obstacle.
     * Equivalent to tcPP with obstacle at origin and zero velocity.
     */
    double tcObs(int i) {
        double dvdr = x[i] * vx[i] + y[i] * vy[i];
        if (dvdr >= 0) return INF;                    // moving away from obstacle
        double dv2 = vx[i] * vx[i] + vy[i] * vy[i];
        double dr2 = x[i] * x[i] + y[i] * y[i];
        double d   = dvdr * dvdr - dv2 * (dr2 - SIGMA_OBS * SIGMA_OBS);
        if (d < 0) return INF;
        double dt = -(dvdr + Math.sqrt(d)) / dv2;
        return dt > EPS ? dt : INF;
    }

    /**
     * Time until particle i hits the outer circular wall from inside.
     * Particle is inside (|pos| < R_WALL_EFF), so we take the larger root of the quadratic.
     */
    double tcWall(int i) {
        double dvdr = x[i] * vx[i] + y[i] * vy[i];
        double dv2  = vx[i] * vx[i] + vy[i] * vy[i];
        double dr2  = x[i] * x[i]   + y[i] * y[i];
        // d > 0 guaranteed for particle strictly inside the wall
        double d = dvdr * dvdr - dv2 * (dr2 - R_WALL_EFF * R_WALL_EFF);
        if (d < 0) return INF;
        double dt = (-dvdr + Math.sqrt(d)) / dv2;  // larger root (exit side)
        return dt > EPS ? dt : INF;
    }

    // ── Event scheduling ──────────────────────────────────────────────────────

    /** Schedule all initial events O(N²). */
    void scheduleAll() {
        for (int i = 0; i < N; i++) {
            addObs(i); addWall(i);
            for (int j = i + 1; j < N; j++) addPP(i, j);
        }
    }

    /** Reschedule all events involving particle i (after i collides). O(N). */
    void scheduleFor(int i) {
        addObs(i); addWall(i);
        for (int j = 0; j < N; j++) { if (j != i) addPP(i, j); }
    }

    void addPP(int i, int j) {
        double dt = tcPP(i, j);
        if (dt < INF) pq.add(new Event(currentTime + dt, EVT_PP, i, j, cc[i], cc[j]));
    }

    void addObs(int i) {
        double dt = tcObs(i);
        if (dt < INF) pq.add(new Event(currentTime + dt, EVT_OBS, i, -1, cc[i], -1));
    }

    void addWall(int i) {
        double dt = tcWall(i);
        if (dt < INF) pq.add(new Event(currentTime + dt, EVT_WALL, i, -1, cc[i], -1));
    }

    /** Event is valid only if collision counts still match. */
    boolean valid(Event e) {
        return cc[e.i()] == e.ci() && (e.type() != EVT_PP || cc[e.j()] == e.cj());
    }

    // ── Collision resolvers ────────────────────────────────────────────────────

    /** Elastic collision between two equal-mass particles. */
    void collidePP(int i, int j) {
        double dx   = x[i] - x[j], dy   = y[i] - y[j];
        double dist = Math.sqrt(dx * dx + dy * dy);
        double nx   = dx / dist,   ny   = dy / dist;
        // Normal component of relative velocity
        double dvn  = (vx[i] - vx[j]) * nx + (vy[i] - vy[j]) * ny;
        vx[i] -= dvn * nx; vy[i] -= dvn * ny;
        vx[j] += dvn * nx; vy[j] += dvn * ny;
        cc[i]++; cc[j]++;
    }

    /** Elastic reflection off the fixed obstacle (infinite mass). Updates state. */
    void collideObs(int i) {
        double dist = Math.sqrt(x[i] * x[i] + y[i] * y[i]);
        double nx   = x[i] / dist, ny = y[i] / dist;
        double vn   = vx[i] * nx + vy[i] * ny;
        vx[i] -= 2 * vn * nx; vy[i] -= 2 * vn * ny;
        cc[i]++;
        if (state[i] == FRESH) { state[i] = USED; Cfc++; }
    }

    /** Elastic reflection off the outer circular wall. Updates state. */
    void collideWall(int i) {
        double dist = Math.sqrt(x[i] * x[i] + y[i] * y[i]);
        double nx   = x[i] / dist, ny = y[i] / dist;
        double vn   = vx[i] * nx + vy[i] * ny;
        vx[i] -= 2 * vn * nx; vy[i] -= 2 * vn * ny;
        cc[i]++;
        if (state[i] == USED) state[i] = FRESH;
    }

    // ── Ballistic advance ─────────────────────────────────────────────────────
    void advance(double newT) {
        double dt = newT - currentTime;
        for (int i = 0; i < N; i++) { x[i] += vx[i] * dt; y[i] += vy[i] * dt; }
        currentTime = newT;
    }

    // ── Output helpers ────────────────────────────────────────────────────────
    void exportFrame(Path dir, long idx) throws IOException {
        Path tmp = dir.resolve(String.format("frame_%05d.txt.tmp", idx));
        Path out = dir.resolve(String.format("frame_%05d.txt",     idx));
        try (var w = Files.newBufferedWriter(tmp)) {
            w.write(String.format("%.6f%n", currentTime));
            for (int i = 0; i < N; i++) {
                w.write(String.format("%.6f\t%.6f\t%.6f\t%.6f\t%d%n",
                        x[i], y[i], vx[i], vy[i], state[i]));
            }
        }
        Files.move(tmp, out, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }

    int countUsed() {
        int c = 0;
        for (int s : state) if (s == USED) c++;
        return c;
    }

    // ── Main simulation loop ──────────────────────────────────────────────────
    /**
     * @param tf          simulation end time
     * @param statsOut    writer for "time Cfc Nu" rows (null = skip)
     * @param framesDir   directory for frame files (null = skip)
     * @param maxFrames   frame cap (0 = skip frames)
     * @param frameEvery  emit a frame every this many events
     */
    void run(double tf, BufferedWriter statsOut, Path framesDir, int maxFrames, int frameEvery)
            throws IOException {
        long eventCount = 0;
        long frameCount = 0;

        if (framesDir != null && maxFrames > 0) exportFrame(framesDir, frameCount++);
        if (statsOut != null) writeStats(statsOut);

        while (true) {
            Event e = pq.peek();
            if (e == null || e.time() > tf) break;
            pq.poll();
            if (!valid(e)) continue;

            advance(e.time());

            switch (e.type()) {
                case EVT_PP   -> { collidePP(e.i(), e.j()); scheduleFor(e.i()); scheduleFor(e.j()); }
                case EVT_OBS  -> { collideObs(e.i());        scheduleFor(e.i()); }
                case EVT_WALL -> { collideWall(e.i());       scheduleFor(e.i()); }
            }

            eventCount++;
            if (statsOut != null) writeStats(statsOut);

            if (framesDir != null && maxFrames > 0
                    && frameCount < maxFrames
                    && eventCount % frameEvery == 0) {
                exportFrame(framesDir, frameCount++);
            }
        }

        // Advance to tf, write final state
        advance(tf);
        if (framesDir != null && maxFrames > 0 && frameCount < maxFrames)
            exportFrame(framesDir, frameCount);
        if (statsOut != null) writeStats(statsOut);
    }

    void writeStats(BufferedWriter w) throws IOException {
        w.write(String.format("%.6f %d %d%n", currentTime, Cfc, countUsed()));
    }

    // ── Utilities ─────────────────────────────────────────────────────────────
    static void recreateDir(Path dir) throws IOException {
        if (Files.exists(dir)) {
            try (var s = Files.newDirectoryStream(dir)) { for (Path p : s) Files.deleteIfExists(p); }
        } else {
            Files.createDirectories(dir);
        }
    }

    static String resolveBinPath() {
        String env = System.getenv("TP3_BIN_PATH");
        if (env != null && !env.isEmpty()) return env;
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp3-bin").toAbsolutePath().normalize().toString();
    }

    // ── Entry point ───────────────────────────────────────────────────────────
    public static void main(String[] args) throws IOException {
        int    n          = 50;
        long   seed       = 42;
        double tf         = 100.0;
        int    maxFrames  = 2000;
        int    frameEvery = 10;
        boolean noStats   = false;
        String binPath    = resolveBinPath();

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--n"           -> n          = Integer.parseInt(args[++i]);
                case "--seed"        -> seed        = Long.parseLong(args[++i]);
                case "--tf"          -> tf          = Double.parseDouble(args[++i]);
                case "--max-frames"  -> maxFrames   = Integer.parseInt(args[++i]);
                case "--frame-every" -> frameEvery  = Integer.parseInt(args[++i]);
                case "--no-stats"    -> noStats     = true;
                case "--bin"         -> binPath     = args[++i];
            }
        }

        Path bin = Paths.get(binPath);
        Files.createDirectories(bin);
        Path framesDir = bin.resolve("frames");
        recreateDir(framesDir);

        long wallStart = System.nanoTime();
        var sim = new EventDrivenMD(n, seed);

        BufferedWriter statsWriter = noStats ? null : Files.newBufferedWriter(bin.resolve("stats.txt"));
        if (statsWriter != null) statsWriter.write("time Cfc Nu\n");

        sim.run(tf, statsWriter, framesDir, maxFrames, frameEvery);

        if (statsWriter != null) statsWriter.close();
        double elapsed = (System.nanoTime() - wallStart) / 1e9;

        try (var mw = Files.newBufferedWriter(bin.resolve("metadata.txt"))) {
            mw.write(String.format("N %d%n", n));
            mw.write(String.format("L %.1f%n", 2 * R_DOMAIN));
            mw.write(String.format("R_domain %.1f%n", R_DOMAIN));
            mw.write(String.format("R_obstacle %.1f%n", R_OBSTACLE));
            mw.write(String.format("R_particle %.1f%n", R_PARTICLE));
            mw.write(String.format("v0 %.1f%n", V0));
            mw.write(String.format("tf %.1f%n", tf));
            mw.write(String.format("seed %d%n", seed));
        }

        System.out.printf("N=%d seed=%d tf=%.1f wall_time=%.3fs%n", n, seed, tf, elapsed);
    }
}
