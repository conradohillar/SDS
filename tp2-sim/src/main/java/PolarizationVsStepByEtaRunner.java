import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Polarizacion promedio vs step para eta = {0,1,2,3,4,5}.
 *
 * Cumple el pedido del usuario:
 * - Sim en un archivo Java.
 * - Vis en un archivo Python.
 * - 1000 pasos por corrida (step=0..steps-1 => 1000 muestras).
 *
 * Output:
 * - tp2-bin/polarization_vs_step_by_eta.csv
 *   Columnas: step, eta_0, eta_1, ..., eta_5
 */
public class PolarizationVsStepByEtaRunner {
    public static void main(String[] args) throws IOException {
        Locale.setDefault(Locale.US);

        long steps = 1000L;
        double etaMin = 0.0;
        double etaMax = 5.0;
        double etaStep = 1.0;
        long seedBase = System.nanoTime();

        Map<String, String> argMap = parseArgs(args);
        steps = getLongOrDefault(argMap, "--steps", steps);
        etaMin = getDoubleOrDefault(argMap, "--eta-min", etaMin);
        etaMax = getDoubleOrDefault(argMap, "--eta-max", etaMax);
        etaStep = getDoubleOrDefault(argMap, "--eta-step", etaStep);
        seedBase = getLongOrDefault(argMap, "--seed-base", seedBase);

        Path binDir = resolveBinPath();
        Files.createDirectories(binDir);

        Path outCsv = binDir.resolve("polarization_vs_step_by_eta.csv");

        double L = 10.0;
        int cellDensity = 4; // rho = 4 => N = L^2 * rho
        long N = (long) Math.pow(L, 2) * cellDensity; // 400

        double rc = 1.0;
        double dt = 1.0;
        boolean periodicBorders = true;
        double velocityModule = 0.03;

        // En tp2-sim (AutomataOffLattice) minParticleRadius=maxParticleRadius=0 => radios y props en 0.
        double minParticleRadius = 0.0;
        double maxParticleRadius = 0.0;
        double property = 0.0;

        List<Double> etas = generateEtaValues(etaMin, etaMax, etaStep);
        int etaCount = etas.size();

        // Simulamos cada eta por separado (misma grilla, distintas semillas).
        // Guardamos una serie por eta.
        double[][] vaSeries = new double[etaCount][(int) steps];

        for (int etaIdx = 0; etaIdx < etaCount; etaIdx++) {
            double eta = etas.get(etaIdx);
            long seed = seedBase + etaIdx * 1_000_003L;
            java.util.Random rng = new java.util.Random(seed);

            List<Particle> particles = generateInitialParticles(
                    N, L, periodicBorders, velocityModule, minParticleRadius, maxParticleRadius, property, rng
            );

            List<Particle> current = particles;
            for (int s = 0; s < steps; s++) {
                vaSeries[etaIdx][s] = computePolarization(current);
                double time = s * dt;
                current = advanceOneStep(
                        current, L, rc, velocityModule, dt, eta, periodicBorders, time, rng
                );
            }

            System.out.printf(Locale.US, "eta=%.3f done%n", eta);
        }

        // Escribir CSV ancho (wide):
        // header: step, eta_<value>, ...
        try (BufferedWriter w = new BufferedWriter(new FileWriter(outCsv.toFile()))) {
            w.write("step");
            for (int etaIdx = 0; etaIdx < etaCount; etaIdx++) {
                // Use actual eta value in the column name so plotting can label correctly.
                w.write(String.format(Locale.US, ",eta_%.6g", etas.get(etaIdx)));
            }
            w.newLine();

            for (int s = 0; s < steps; s++) {
                w.write(Integer.toString(s));
                for (int etaIdx = 0; etaIdx < etaCount; etaIdx++) {
                    w.write(String.format(Locale.US, ",%.12f", vaSeries[etaIdx][s]));
                }
                w.newLine();
            }
        }

        // Mensaje con eta real asociado a cada columna.
        System.out.printf(Locale.US, "Wrote: %s%n", outCsv.toAbsolutePath());
        System.out.printf(Locale.US, "Columns mapping (etaIdx -> eta):%n");
        for (int i = 0; i < etaCount; i++) {
            System.out.printf(Locale.US, "  %d -> %.3f%n", i, etas.get(i));
        }
    }

    private static List<Double> generateEtaValues(double etaMin, double etaMax, double etaStep) {
        int count = (int) Math.round((etaMax - etaMin) / etaStep);
        List<Double> etas = new ArrayList<>(count + 1);
        for (int i = 0; i <= count; i++) {
            etas.add(etaMin + i * etaStep);
        }
        etas.sort(Comparator.naturalOrder());
        return etas;
    }

    private static List<Particle> generateInitialParticles(long N,
                                                             double L,
                                                             boolean periodicBorders,
                                                             double velocityModule,
                                                             double minParticleRadius,
                                                             double maxParticleRadius,
                                                             double property,
                                                             java.util.Random rng) {
        List<Particle> particles = new ArrayList<>((int) N);
        for (int i = 0; i < N; i++) {
            double radius = rng.nextDouble() * (maxParticleRadius - minParticleRadius) + minParticleRadius; // => 0 en tp2
            double minPos = periodicBorders ? 0.0 : radius;
            double maxPos = periodicBorders ? L : L - radius;
            double x = rng.nextDouble() * (maxPos - minPos) + minPos;
            double y = rng.nextDouble() * (maxPos - minPos) + minPos;

            double angle = rng.nextDouble() * 2.0 * Math.PI;
            double vx = velocityModule * Math.cos(angle);
            double vy = velocityModule * Math.sin(angle);

            particles.add(new Particle(i + 1L, x, y, vx, vy, radius, property));
        }
        return particles;
    }

    private static List<Particle> advanceOneStep(List<Particle> particles,
                                                 double L,
                                                 double rc,
                                                 double velocityModule,
                                                 double dt,
                                                 double eta,
                                                 boolean periodicBorders,
                                                 double time,
                                                 java.util.Random rng) {
        // Vecinos del estado actual (t).
        CellIndexMethodNeighborFinder cim = new CellIndexMethodNeighborFinder(particles.size(), L, rc, periodicBorders, particles);
        cim.findNeighbors();
        Map<Particle, List<Particle>> neighborMap = cim.particleNeighborsMap;

        List<Particle> next = new ArrayList<>(particles.size());

        for (Particle p : particles) {
            // Leader NONE: no hay caso especial.

            // Standard Vicsek update.
            List<Particle> neighbors = neighborMap.getOrDefault(p, List.of());

            double sumSin = Math.sin(angle(p));
            double sumCos = Math.cos(angle(p));

            for (Particle n : neighbors) {
                sumSin += Math.sin(angle(n));
                sumCos += Math.cos(angle(n));
            }

            double avgTheta = Math.atan2(sumSin, sumCos);
            // Uniform in [-eta/2, eta/2]
            double noise = (rng.nextDouble() - 0.5) * eta;
            double newTheta = avgTheta + noise;

            double vx = velocityModule * Math.cos(newTheta);
            double vy = velocityModule * Math.sin(newTheta);

            double newX = p.x() + vx * dt;
            double newY = p.y() + vy * dt;

            if (periodicBorders) {
                newX = modPos(newX, L);
                newY = modPos(newY, L);
            } else {
                newX = Math.max(0.0, Math.min(L, newX));
                newY = Math.max(0.0, Math.min(L, newY));
            }

            next.add(new Particle(p.id(), newX, newY, vx, vy, p.radius(), p.property()));
        }

        return next;
    }

    private static double computePolarization(List<Particle> particles) {
        int n = particles.size();
        double sumUx = 0.0;
        double sumUy = 0.0;

        for (Particle p : particles) {
            double speed = Math.hypot(p.vx(), p.vy());
            if (speed > 0.0) {
                sumUx += p.vx() / speed;
                sumUy += p.vy() / speed;
            }
        }

        double sx = sumUx / n;
        double sy = sumUy / n;
        return Math.hypot(sx, sy);
    }

    private static double angle(Particle p) {
        return Math.atan2(p.vy(), p.vx());
    }

    private static double modPos(double x, double L) {
        return ((x % L) + L) % L;
    }

    private static Path resolveBinPath() {
        String fromEnv = System.getenv("TP2_BIN_PATH");
        if (fromEnv != null && !fromEnv.isEmpty()) {
            return Paths.get(fromEnv).toAbsolutePath().normalize();
        }
        return Paths.get(System.getProperty("user.dir"))
                .resolve("tp2-bin")
                .toAbsolutePath()
                .normalize();
    }

    private static Map<String, String> parseArgs(String[] args) {
        // Parser minimal: soporta flags de la forma --key value y --key=value.
        java.util.TreeMap<String, String> map = new java.util.TreeMap<>();
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            if (!arg.startsWith("--")) continue;

            if (arg.contains("=")) {
                String[] parts = arg.split("=", 2);
                map.put(parts[0], parts[1]);
            } else {
                String key = arg;
                if (i + 1 < args.length && !args[i + 1].startsWith("--")) {
                    map.put(key, args[i + 1]);
                    i++;
                }
            }
        }
        return map;
    }

    private static long getLongOrDefault(Map<String, String> map, String key, long defaultValue) {
        String v = map.get(key);
        if (v == null) return defaultValue;
        return Long.parseLong(v);
    }

    private static double getDoubleOrDefault(Map<String, String> map, String key, double defaultValue) {
        String v = map.get(key);
        if (v == null) return defaultValue;
        return Double.parseDouble(v);
    }
}

