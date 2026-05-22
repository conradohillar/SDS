import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * TP5 Sistema 3 – Time-Driven Active Matter (RK4).
 *
 * Self-propelled particles of radius r_p in a circular domain of radius R.
 * Overdamped first-order dynamics:
 *   dx_i/dt = v0*cos(α_i) + Σ_j F_ij,x + F_wall,i,x
 *   dy_i/dt = v0*sin(α_i) + Σ_j F_ij,y + F_wall,i,y
 *   dα_i/dt = σ_i * |v_i| / r_p + η_i
 *
 * Repulsion: F_ij = -κ·ε_ij·ρ̂_ij  (ρ̂_ij from i toward j, ε = 2r_p − d when d < 2r_p)
 * Wall:      F_wi = -κ·ε_wi·r̂_i    (ε_w = |r_i| − (R−r_p) when positive; pushes inward)
 *
 * Modes:
 *   quiral – σ_i = +1 fixed
 *   random – σ_i ∈ {±1} independently resampled every 1 s
 *
 * Output every dt2 seconds:
 *   frames/frame_NNNNNN.txt  – line 1: t; lines 2..N+1: "x y vx vy alpha sigma"
 *   stats.txt                – t  v_mean  P_wall  n_contacts
 *   metadata.txt             – key-value parameters
 *
 * CLI:
 *   --n         <int>     particles (default 20)
 *   --seed      <long>    RNG seed (default 42)
 *   --mode      <string>  quiral | random (default quiral)
 *   --dt        <double>  integration step [s] (default 0.01)
 *   --tf        <double>  final time [s] (default 10000)
 *   --dt2       <double>  output interval [s] (default 0.1)
 *   --no-frames           skip writing frame files
 *   --bin       <path>    output base dir (default ../tp5-bin)
 *   --run-id    <string>  sub-directory name (default "default")
 */
public class TimeDrivenActive {

    // ── Physical constants ────────────────────────────────────────────────────
    static final double R_P       = 1.6;
    static final double R_DOMAIN  = 10.0;
    static final double V0        = 0.825;
    static final double KAPPA     = 50.0;
    static final double SIGMA_ETA = 0.05;
    static final double SIGMA_PP  = 2.0 * R_P;
    static final double R_EFF     = R_DOMAIN - R_P;
    static final double TWO_PI_R  = 2.0 * Math.PI * R_DOMAIN;

    // ── State ─────────────────────────────────────────────────────────────────
    final int    n;
    final String mode;
    double[] x, y, alpha;
    int[]    sigma;
    final Random rng;

    // Pre-allocated RK4 workspace
    final double[] fx, fy;
    final double[] k1x, k1y, k1a;
    final double[] k2x, k2y, k2a;
    final double[] k3x, k3y, k3a;
    final double[] k4x, k4y, k4a;
    final double[] xt, yt, at;
    final double[] eta;

    TimeDrivenActive(int n, long seed, String mode) {
        this.n = n; this.mode = mode; this.rng = new Random(seed);
        x=new double[n]; y=new double[n]; alpha=new double[n];
        sigma=new int[n];
        fx=new double[n]; fy=new double[n];
        k1x=new double[n]; k1y=new double[n]; k1a=new double[n];
        k2x=new double[n]; k2y=new double[n]; k2a=new double[n];
        k3x=new double[n]; k3y=new double[n]; k3a=new double[n];
        k4x=new double[n]; k4y=new double[n]; k4a=new double[n];
        xt=new double[n]; yt=new double[n]; at=new double[n];
        eta=new double[n];
        placeParticles();
        for (int i=0;i<n;i++) alpha[i] = 2*Math.PI*rng.nextDouble();
        resampleSigma();
    }

    void resampleSigma() {
        if (mode.equals("quiral")) { Arrays.fill(sigma, 1); }
        else { for (int i=0;i<n;i++) sigma[i] = rng.nextBoolean() ? 1 : -1; }
    }

    static class Pt { double x, y; Pt(double x, double y){this.x=x; this.y=y;} }

    static List<Pt> hexGrid(double step, double radius) {
        double dx = step, dy = step * Math.sqrt(3.0) / 2.0;
        List<Pt> pts = new ArrayList<>();
        int iMax = (int) Math.ceil(radius / dy) + 1;
        int jMax = (int) Math.ceil(radius / dx) + 1;
        for (int i = -iMax; i <= iMax; i++) {
            double yi = i * dy;
            double xOff = (Math.abs(i) % 2 == 1) ? dx/2.0 : 0.0;
            for (int j = -jMax; j <= jMax; j++) {
                double xi = j * dx + xOff;
                if (Math.sqrt(xi*xi + yi*yi) <= radius - 0.01)
                    pts.add(new Pt(xi, yi));
            }
        }
        return pts;
    }

    void placeParticles() {
        // Find smallest hexagonal grid step that yields ≥ n candidate positions.
        // Start at SIGMA_PP and reduce by 10 % per iteration until enough slots exist.
        // Positions may initially overlap; elastic forces resolve that in the first steps.
        double step = SIGMA_PP;
        List<Pt> candidates = null;
        for (int attempt = 0; attempt < 30; attempt++) {
            List<Pt> c = hexGrid(step, R_EFF);
            if (c.size() >= n) { candidates = c; break; }
            step *= 0.90;
        }
        if (candidates == null)
            throw new RuntimeException("Cannot generate " + n + " positions for N=" + n);
        Collections.shuffle(candidates, rng);
        for (int i=0; i<n; i++) { x[i]=candidates.get(i).x; y[i]=candidates.get(i).y; }
    }

    // ── Force computation ─────────────────────────────────────────────────────
    void computeForces(double[] xs, double[] ys, double[] fxOut, double[] fyOut) {
        Arrays.fill(fxOut, 0.0);
        Arrays.fill(fyOut, 0.0);
        // Particle-particle repulsion
        for (int i=0; i<n-1; i++) {
            for (int j=i+1; j<n; j++) {
                double dx = xs[j]-xs[i], dy = ys[j]-ys[i];
                double d2 = dx*dx + dy*dy;
                if (d2 < SIGMA_PP*SIGMA_PP && d2 > 1e-20) {
                    double d    = Math.sqrt(d2);
                    double fmag = -KAPPA*(SIGMA_PP-d)/d; // negative → F in -(j-i) direction = repulsive on i
                    fxOut[i] += fmag*dx; fyOut[i] += fmag*dy;
                    fxOut[j] -= fmag*dx; fyOut[j] -= fmag*dy;
                }
            }
        }
        // Wall repulsion (inward)
        for (int i=0; i<n; i++) {
            double r = Math.sqrt(xs[i]*xs[i] + ys[i]*ys[i]);
            if (r > R_EFF && r > 1e-10) {
                double fmag = -KAPPA*(r-R_EFF)/r;
                fxOut[i] += fmag*xs[i];
                fyOut[i] += fmag*ys[i];
            }
        }
    }

    // ── Derivative evaluation ─────────────────────────────────────────────────
    void evalDerivs(double[] xs, double[] ys, double[] alphas,
                    double[] fxArg, double[] fyArg,
                    double[] dxOut, double[] dyOut, double[] daOut) {
        for (int i=0; i<n; i++) {
            dxOut[i] = V0*Math.cos(alphas[i]) + fxArg[i];
            dyOut[i] = V0*Math.sin(alphas[i]) + fyArg[i];
            double vi = Math.sqrt(dxOut[i]*dxOut[i] + dyOut[i]*dyOut[i]);
            daOut[i] = sigma[i]*vi/R_P + eta[i];
        }
    }

    // ── RK4 step ──────────────────────────────────────────────────────────────
    void stepRK4(double dt) {
        double h2 = 0.5*dt, h6 = dt/6.0;
        for (int i=0;i<n;i++) eta[i] = rng.nextGaussian()*SIGMA_ETA;

        computeForces(x,  y,  fx, fy);
        evalDerivs(x, y, alpha, fx, fy, k1x, k1y, k1a);

        for (int i=0;i<n;i++){xt[i]=x[i]+h2*k1x[i]; yt[i]=y[i]+h2*k1y[i]; at[i]=alpha[i]+h2*k1a[i];}
        computeForces(xt, yt, fx, fy);
        evalDerivs(xt, yt, at, fx, fy, k2x, k2y, k2a);

        for (int i=0;i<n;i++){xt[i]=x[i]+h2*k2x[i]; yt[i]=y[i]+h2*k2y[i]; at[i]=alpha[i]+h2*k2a[i];}
        computeForces(xt, yt, fx, fy);
        evalDerivs(xt, yt, at, fx, fy, k3x, k3y, k3a);

        for (int i=0;i<n;i++){xt[i]=x[i]+dt*k3x[i]; yt[i]=y[i]+dt*k3y[i]; at[i]=alpha[i]+dt*k3a[i];}
        computeForces(xt, yt, fx, fy);
        evalDerivs(xt, yt, at, fx, fy, k4x, k4y, k4a);

        for (int i=0;i<n;i++){
            x[i]     += h6*(k1x[i]+2*k2x[i]+2*k3x[i]+k4x[i]);
            y[i]     += h6*(k1y[i]+2*k2y[i]+2*k3y[i]+k4y[i]);
            alpha[i] += h6*(k1a[i]+2*k2a[i]+2*k3a[i]+k4a[i]);
        }
    }

    // ── Observables ───────────────────────────────────────────────────────────
    // Returns {v_mean, P_wall, n_contacts} and fills vxOut, vyOut.
    double[] computeObservables(double[] vxOut, double[] vyOut) {
        computeForces(x, y, fx, fy);
        double vSum=0, wallSum=0;
        int contacts=0;
        for (int i=0;i<n;i++){
            vxOut[i] = V0*Math.cos(alpha[i]) + fx[i];
            vyOut[i] = V0*Math.sin(alpha[i]) + fy[i];
            vSum += Math.sqrt(vxOut[i]*vxOut[i] + vyOut[i]*vyOut[i]);
        }
        for (int i=0;i<n;i++){
            double r = Math.sqrt(x[i]*x[i]+y[i]*y[i]);
            if (r > R_EFF) wallSum += KAPPA*(r-R_EFF);
        }
        for (int i=0;i<n-1;i++) for (int j=i+1;j<n;j++){
            double dx=x[j]-x[i], dy=y[j]-y[i];
            if (dx*dx+dy*dy < SIGMA_PP*SIGMA_PP) contacts++;
        }
        return new double[]{vSum/n, wallSum/TWO_PI_R, contacts};
    }

    // ── I/O ───────────────────────────────────────────────────────────────────
    static PrintWriter open(Path p) throws IOException {
        Files.createDirectories(p.getParent());
        return new PrintWriter(Files.newBufferedWriter(p));
    }

    static void writeFrame(Path dir, int idx, double t,
                           double[] xs, double[] ys, double[] vxs, double[] vys,
                           double[] alphas, int[] sigmas, int n) throws IOException {
        try (PrintWriter w = open(dir.resolve(String.format("frame_%06d.txt", idx)))) {
            w.printf("%.6f%n", t);
            for (int i=0;i<n;i++)
                w.printf("%.6f %.6f %.6f %.6f %.6f %d%n",
                    xs[i], ys[i], vxs[i], vys[i], alphas[i], sigmas[i]);
        }
    }

    // ── Simulation loop ───────────────────────────────────────────────────────
    static void run(int n, long seed, String mode, double dt, double tf, double dt2,
                    boolean noFrames, Path outDir) throws IOException {
        Files.createDirectories(outDir);
        Path framesDir = outDir.resolve("frames");
        if (!noFrames) {
            Files.createDirectories(framesDir);
            try (var ds = Files.newDirectoryStream(framesDir, "frame_*.txt")) {
                for (Path f : ds) Files.delete(f);
            }
        }

        TimeDrivenActive sim = new TimeDrivenActive(n, seed, mode);
        double[] vxBuf = new double[n], vyBuf = new double[n];

        PrintWriter wStats = open(outDir.resolve("stats.txt"));
        wStats.println("t v_mean P_wall n_contacts");

        int stepsPerOut  = Math.max(1, (int) Math.round(dt2/dt));
        int totalSteps   = (int) Math.ceil(tf/dt);
        int sigmaInterval = (int) Math.round(1.0/dt);
        int frameIdx = 0;

        // t = 0
        double[] obs0 = sim.computeObservables(vxBuf, vyBuf);
        if (!noFrames)
            writeFrame(framesDir, frameIdx++, 0.0, sim.x, sim.y, vxBuf, vyBuf, sim.alpha, sim.sigma, n);
        wStats.printf("%.4f %.8f %.8f %d%n", 0.0, obs0[0], obs0[1], (int)obs0[2]);

        for (int s=1; s<=totalSteps; s++) {
            if (mode.equals("random") && s % sigmaInterval == 0)
                sim.resampleSigma();
            sim.stepRK4(dt);
            if (s % stepsPerOut == 0) {
                double t = s*dt;
                double[] obs = sim.computeObservables(vxBuf, vyBuf);
                if (!noFrames)
                    writeFrame(framesDir, frameIdx++, t, sim.x, sim.y, vxBuf, vyBuf, sim.alpha, sim.sigma, n);
                wStats.printf("%.4f %.8f %.8f %d%n", t, obs[0], obs[1], (int)obs[2]);
                if (s % (stepsPerOut*1000) == 0) wStats.flush();
            }
        }
        wStats.close();

        try (PrintWriter wM = open(outDir.resolve("metadata.txt"))) {
            wM.printf("N %d%n",      n);
            wM.printf("mode %s%n",   mode);
            wM.printf("seed %d%n",   seed);
            wM.printf("dt %.6e%n",   dt);
            wM.printf("dt2 %.6e%n",  dt2);
            wM.printf("tf %.2f%n",   tf);
            wM.printf("r_p %.4f%n",  R_P);
            wM.printf("R %.4f%n",    R_DOMAIN);
            wM.printf("v0 %.6f%n",   V0);
            wM.printf("kappa %.4f%n", KAPPA);
            wM.printf("sigma_eta %.4f%n", SIGMA_ETA);
        }
    }

    static String resolveBin() {
        String e = System.getenv("TP5_BIN_PATH");
        if (e != null && !e.isEmpty()) return e;
        return Paths.get(System.getProperty("user.dir"))
            .resolve("../tp5-bin").toAbsolutePath().normalize().toString();
    }

    // ── Entry point ───────────────────────────────────────────────────────────
    public static void main(String[] args) throws IOException {
        int n=20; long seed=42L; String mode="quiral";
        double dt=0.01, tf=10000.0, dt2=0.1;
        boolean noFrames=false;
        String binPath=resolveBin(), runId="default";

        for (int i=0;i<args.length;i++) switch (args[i]) {
            case "--n"         -> n        = Integer.parseInt(args[++i]);
            case "--seed"      -> seed     = Long.parseLong(args[++i]);
            case "--mode"      -> mode     = args[++i];
            case "--dt"        -> dt       = Double.parseDouble(args[++i]);
            case "--tf"        -> tf       = Double.parseDouble(args[++i]);
            case "--dt2"       -> dt2      = Double.parseDouble(args[++i]);
            case "--no-frames" -> noFrames = true;
            case "--bin"       -> binPath  = args[++i];
            case "--run-id"    -> runId    = args[++i];
        }

        Path outDir = Paths.get(binPath).resolve(runId);
        System.out.printf("TimeDrivenActive N=%d mode=%s seed=%d dt=%.2e tf=%.1f%n",
            n, mode, seed, dt, tf);
        System.out.printf("Output → %s%n", outDir);
        long t0 = System.currentTimeMillis();
        run(n, seed, mode, dt, tf, dt2, noFrames, outDir);
        System.out.printf("Done in %.2f s%n", (System.currentTimeMillis()-t0)/1000.0);
    }
}
