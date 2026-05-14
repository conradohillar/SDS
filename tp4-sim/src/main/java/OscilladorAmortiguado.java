import java.io.*;
import java.nio.file.*;

/**
 * TP4 Sistema 1 – Oscilador Puntual Amortiguado.
 *
 * Ecuación: f = ma = -k*r - gamma*v
 * Parámetros (diapositiva 36): m=70 kg, k=1e4 N/m, gamma=100 kg/s, tf=5 s
 * Condiciones iniciales: r(0)=1 m, v(0)=-A*gamma/(2m)  con A=1
 * Solución analítica: r(t) = A*exp(-gamma/(2m)*t) * cos(omega*t)
 *   donde omega = sqrt(k/m - gamma^2/(4m^2))
 *
 * Integradores: Euler, Verlet original, Beeman, Gear predictor-corrector orden 5
 *
 * Modos de uso:
 *   --mode trajectory  (default) escribe archivos de trayectoria para un dt fijo
 *   --mode ecm         calcula ECM vs dt para cada integrador
 *
 * CLI:
 *   --mode  <trajectory|ecm>
 *   --dt    <double>   paso temporal (default 1e-4)
 *   --tf    <double>   tiempo final  (default 5.0)
 *   --bin   <path>     directorio de salida (default ../tp4-bin)
 */
public class OscilladorAmortiguado {

    // ── Parámetros físicos ─────────────────────────────────────────────────────
    static final double M     = 70.0;
    static final double K     = 1e4;
    static final double GAMMA = 100.0;
    static final double A     = 1.0;
    static final double R0    = 1.0;
    static final double V0    = -A * GAMMA / (2.0 * M);   // ≈ -0.7143 m/s

    // Gear orden 5 – coeficientes para fuerzas que dependen de r y v (diap. 29)
    static final double[] ALPHA = {3.0/16, 251.0/360, 1.0, 11.0/18, 1.0/6, 1.0/60};

    // ── Fuerza y solución analítica ───────────────────────────────────────────
    static double force(double r, double v) {
        return -K * r - GAMMA * v;
    }

    static double analytical(double t) {
        double omega = Math.sqrt(K / M - GAMMA * GAMMA / (4.0 * M * M));
        return A * Math.exp(-GAMMA / (2.0 * M) * t) * Math.cos(omega * t);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  ECM runners (no escritura a disco – solo valor escalar)
    // ═══════════════════════════════════════════════════════════════════════════

    static double ecmEuler(double dt, double tf) {
        int n = (int) Math.ceil(tf / dt);
        double r = R0, v = V0, ecm = 0;
        for (int i = 1; i <= n; i++) {
            double f = force(r, v);
            r += dt * v + dt * dt / (2 * M) * f;
            v += dt / M * f;
            double d = r - analytical(i * dt);
            ecm += d * d;
        }
        return ecm / n;
    }

    static double ecmVerlet(double dt, double tf) {
        int n = (int) Math.ceil(tf / dt);
        double r = R0, v = V0;
        // Arranque: r(-dt) via Euler hacia atrás
        double f0   = force(r, v);
        double rPrev = r - dt * v + dt * dt / (2 * M) * f0;
        double ecm  = 0;
        for (int i = 1; i <= n; i++) {
            double vApprox = (r - rPrev) / dt;   // diferencia regresiva O(dt)
            double f       = force(r, vApprox);
            double rNext   = 2 * r - rPrev + dt * dt / M * f;
            v    = (rNext - rPrev) / (2 * dt);   // velocidad centrada (solo para energía)
            rPrev = r; r = rNext;
            double d = r - analytical(i * dt);
            ecm += d * d;
        }
        return ecm / n;
    }

    static double ecmBeeman(double dt, double tf) {
        int n = (int) Math.ceil(tf / dt);
        double r = R0, v = V0;
        double aCurr = force(r, v) / M;
        // Arranque: a(t-dt) via Euler hacia atrás
        double rPrev = r - dt * v + dt * dt / 2 * aCurr;
        double vPrev = v - dt * aCurr;
        double aPrev = force(rPrev, vPrev) / M;
        double ecm   = 0;
        for (int i = 1; i <= n; i++) {
            double rNext = r + v * dt + (2.0/3 * aCurr - 1.0/6 * aPrev) * dt * dt;
            // velocidad predicha para evaluar la fuerza en t+dt
            double vPred = v + (3.0/2 * aCurr - 1.0/2 * aPrev) * dt;
            double aNext = force(rNext, vPred) / M;
            double vNext = v + (1.0/3 * aNext + 5.0/6 * aCurr - 1.0/6 * aPrev) * dt;
            aPrev = aCurr; aCurr = aNext;
            r = rNext; v = vNext;
            double d = r - analytical(i * dt);
            ecm += d * d;
        }
        return ecm / n;
    }

    static double ecmGear(double dt, double tf) {
        int n = (int) Math.ceil(tf / dt);
        // Estado Gear: r0=r, r1=v, r2=a, r3=da/dt, r4=d2a/dt2, r5=d3a/dt3
        double g0 = R0, g1 = V0;
        double g2 = force(g0, g1) / M;
        double g3 = (-K * g1 - GAMMA * g2) / M;
        double g4 = (-K * g2 - GAMMA * g3) / M;
        double g5 = (-K * g3 - GAMMA * g4) / M;
        double ecm = 0;
        for (int i = 1; i <= n; i++) {
            double dt2=dt*dt, dt3=dt2*dt, dt4=dt3*dt, dt5=dt4*dt;
            // Predicción (Taylor)
            double p0 = g0 + g1*dt + g2*dt2/2 + g3*dt3/6 + g4*dt4/24 + g5*dt5/120;
            double p1 = g1 + g2*dt + g3*dt2/2 + g4*dt3/6 + g5*dt4/24;
            double p2 = g2 + g3*dt + g4*dt2/2 + g5*dt3/6;
            double p3 = g3 + g4*dt + g5*dt2/2;
            double p4 = g4 + g5*dt;
            double p5 = g5;
            // Evaluación
            double aNew = force(p0, p1) / M;
            double dR2  = (aNew - p2) * dt2 / 2;
            // Corrección
            g0 = p0 + ALPHA[0] * dR2;
            g1 = p1 + ALPHA[1] * dR2 / dt;
            g2 = p2 + ALPHA[2] * dR2 * 2   / dt2;
            g3 = p3 + ALPHA[3] * dR2 * 6   / dt3;
            g4 = p4 + ALPHA[4] * dR2 * 24  / dt4;
            g5 = p5 + ALPHA[5] * dR2 * 120 / dt5;
            double d = g0 - analytical(i * dt);
            ecm += d * d;
        }
        return ecm / n;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  Modo trayectoria (escribe todos los integradores + analítica a disco)
    // ═══════════════════════════════════════════════════════════════════════════

    static void writeTrajectory(double dt, double tf, Path outDir) throws IOException {
        int n = (int) Math.ceil(tf / dt);
        Files.createDirectories(outDir);

        // Estados iniciales
        double rE = R0, vE = V0;

        double rV = R0, vV = V0;
        double f0V  = force(rV, vV);
        double rVPr = rV - dt*vV + dt*dt/(2*M)*f0V;

        double rB = R0, vB = V0;
        double aBCurr = force(rB, vB) / M;
        double rBPr   = rB - dt*vB + dt*dt/2*aBCurr;
        double vBPr   = vB - dt*aBCurr;
        double aBPrev = force(rBPr, vBPr) / M;

        double g0 = R0, g1 = V0;
        double g2 = force(g0, g1) / M;
        double g3 = (-K*g1 - GAMMA*g2) / M;
        double g4 = (-K*g2 - GAMMA*g3) / M;
        double g5 = (-K*g3 - GAMMA*g4) / M;

        try (var wA = open(outDir, "analytical.txt");
             var wE = open(outDir, "euler.txt");
             var wV = open(outDir, "verlet.txt");
             var wB = open(outDir, "beeman.txt");
             var wG = open(outDir, "gear.txt")) {

            for (var w : new PrintWriter[]{wA, wE, wV, wB, wG}) w.println("t r");

            row(wA, 0, analytical(0)); row(wE, 0, rE);
            row(wV, 0, rV);           row(wB, 0, rB); row(wG, 0, g0);

            for (int i = 1; i <= n; i++) {
                double t = i * dt;
                row(wA, t, analytical(t));

                // Euler
                double fE = force(rE, vE);
                rE += dt*vE + dt*dt/(2*M)*fE;
                vE += dt/M*fE;
                row(wE, t, rE);

                // Verlet original
                double vAp  = (rV - rVPr) / dt;   // velocidad aproximada
                double fV2  = force(rV, vAp);
                double rVNx = 2*rV - rVPr + dt*dt/M*fV2;
                vV   = (rVNx - rVPr) / (2*dt);
                rVPr = rV; rV = rVNx;
                row(wV, t, rV);

                // Beeman
                double rBNx = rB + vB*dt + (2.0/3*aBCurr - 1.0/6*aBPrev)*dt*dt;
                double vBPd = vB + (3.0/2*aBCurr - 1.0/2*aBPrev)*dt;
                double aBNx = force(rBNx, vBPd) / M;
                double vBNx = vB + (1.0/3*aBNx + 5.0/6*aBCurr - 1.0/6*aBPrev)*dt;
                aBPrev = aBCurr; aBCurr = aBNx;
                rB = rBNx; vB = vBNx;
                row(wB, t, rB);

                // Gear orden 5
                double dt2=dt*dt, dt3=dt2*dt, dt4=dt3*dt, dt5=dt4*dt;
                double p0 = g0+g1*dt+g2*dt2/2+g3*dt3/6+g4*dt4/24+g5*dt5/120;
                double p1 = g1+g2*dt+g3*dt2/2+g4*dt3/6+g5*dt4/24;
                double p2 = g2+g3*dt+g4*dt2/2+g5*dt3/6;
                double p3 = g3+g4*dt+g5*dt2/2;
                double p4 = g4+g5*dt;
                double p5 = g5;
                double aN  = force(p0, p1) / M;
                double dR  = (aN - p2)*dt2/2;
                g0 = p0+ALPHA[0]*dR;
                g1 = p1+ALPHA[1]*dR/dt;
                g2 = p2+ALPHA[2]*dR*2/dt2;
                g3 = p3+ALPHA[3]*dR*6/dt3;
                g4 = p4+ALPHA[4]*dR*24/dt4;
                g5 = p5+ALPHA[5]*dR*120/dt5;
                row(wG, t, g0);
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  Modo ECM vs dt
    // ═══════════════════════════════════════════════════════════════════════════

    static void runECMStudy(double tf, Path outDir) throws IOException {
        double[] dts = {1e-1, 5e-2, 1e-2, 5e-3, 1e-3, 5e-4, 1e-4, 5e-5, 1e-5, 5e-6, 1e-6};
        Files.createDirectories(outDir);
        try (var w = open(outDir, "ecm_vs_dt.txt")) {
            w.println("dt ecm_euler ecm_verlet ecm_beeman ecm_gear");
            for (double dt : dts) {
                double eE = ecmEuler(dt, tf);
                double eV = ecmVerlet(dt, tf);
                double eB = ecmBeeman(dt, tf);
                double eG = ecmGear(dt, tf);
                w.printf("%.2e %.8e %.8e %.8e %.8e%n", dt, eE, eV, eB, eG);
                System.out.printf("dt=%.2e  ECM: Euler=%.3e  Verlet=%.3e  Beeman=%.3e  Gear=%.3e%n",
                        dt, eE, eV, eB, eG);
            }
        }
        System.out.println("Estudio ECM completo → " + outDir.resolve("ecm_vs_dt.txt"));
    }

    // ── Utilidades ────────────────────────────────────────────────────────────
    static PrintWriter open(Path dir, String name) throws IOException {
        return new PrintWriter(Files.newBufferedWriter(dir.resolve(name)));
    }

    static void row(PrintWriter w, double t, double r) {
        w.printf("%.8f %.10f%n", t, r);
    }

    static String resolveBin() {
        String env = System.getenv("TP4_BIN_PATH");
        if (env != null && !env.isEmpty()) return env;
        return Paths.get(System.getProperty("user.dir"))
                .resolve("../tp4-bin").toAbsolutePath().normalize().toString();
    }

    // ── Punto de entrada ──────────────────────────────────────────────────────
    public static void main(String[] args) throws IOException {
        String mode    = "trajectory";
        double dt      = 1e-4;
        double tf      = 5.0;
        String binPath = resolveBin();

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--mode" -> mode    = args[++i];
                case "--dt"   -> dt      = Double.parseDouble(args[++i]);
                case "--tf"   -> tf      = Double.parseDouble(args[++i]);
                case "--bin"  -> binPath = args[++i];
            }
        }

        Path oscDir = Paths.get(binPath).resolve("oscillator");

        if (mode.equals("ecm")) {
            runECMStudy(tf, oscDir);
        } else {
            writeTrajectory(dt, tf, oscDir);
            System.out.printf("Trayectorias → %s  (dt=%.2e, tf=%.1f s)%n", oscDir, dt, tf);
        }
    }
}
