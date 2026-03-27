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
import java.util.stream.Collectors;

/**
 * Polarizacion promedio vs step para eta = {0,1,2,3,4,5}.
 *
 * Soporta lider:
 * - defecto (sin flags): `--leader-none` no aplica (equivale a `LeaderType.NONE`)
 * - `--leader-fixed`: lider de direccion fija (id=1 no se alinea y sigue su direccion constante)
 * - `--leader-circular`: lider con trayectoria circular deterministica (id=1 en circulo de radio R=5)
 *
 * Cumple el pedido del usuario:
 * - Sim en un archivo Java.
 * - Vis en un archivo Python.
 * - 1000 pasos por corrida (step=0..steps-1 => 1000 muestras).
 *
 * Output:
 * - tp2-bin/polarization_vs_step_by_eta.csv
 *   Columnas: step, eta_<value>_run_<idx>, ...
 */
public class PolarizationVsStepByEtaRunner {
    private static final long LEADER_ID = 1L;

    private enum LeaderType {
        NONE,
        FIXED_DIRECTION,
        CIRCULAR_TRAJECTORY
    }

    private static final class CircularLeaderConfig {
        private final double cx;
        private final double cy;
        private final double radius;
        private final double phi0;   // phase at time t=0
        private final double omega;  // angular velocity

        private CircularLeaderConfig(double cx, double cy, double radius, double phi0, double omega) {
            this.cx = cx;
            this.cy = cy;
            this.radius = radius;
            this.phi0 = phi0;
            this.omega = omega;
        }
    }

    public static void main(String[] args) throws IOException {
        Locale.setDefault(Locale.US);

        long steps = 1000L;
        double etaMin = 0.0;
        double etaMax = 5.0;
        double etaStep = 1.0;
        long seedBase = System.nanoTime();
        int runsPerEta = 1;
        double density = 4.0;

        LeaderType leaderType = LeaderType.NONE;
        boolean leaderFixedProvided = false;
        boolean leaderCircularProvided = false;
        for (String arg : args) {
            if ("--leader-fixed".equals(arg)) {
                leaderFixedProvided = true;
            } else if ("--leader-circular".equals(arg)) {
                leaderCircularProvided = true;
            }
        }
        if (leaderFixedProvided && leaderCircularProvided) {
            throw new IllegalArgumentException("Use only one: --leader-fixed or --leader-circular");
        } else if (leaderFixedProvided) {
            leaderType = LeaderType.FIXED_DIRECTION;
        } else if (leaderCircularProvided) {
            leaderType = LeaderType.CIRCULAR_TRAJECTORY;
        }

        Map<String, String> argMap = parseArgs(args);
        steps = getLongOrDefault(argMap, "--steps", steps);
        boolean hasEtas = argMap.containsKey("--etas");
        boolean hasEtaMin = argMap.containsKey("--eta-min");
        boolean hasEtaMax = argMap.containsKey("--eta-max");
        boolean hasEtaStep = argMap.containsKey("--eta-step");
        if (hasEtas && (hasEtaMin || hasEtaMax || hasEtaStep)) {
            throw new IllegalArgumentException("When using --etas, do not define --eta-min, --eta-max or --eta-step");
        }
        if (!hasEtas) {
            etaMin = getDoubleOrDefault(argMap, "--eta-min", etaMin);
            etaMax = getDoubleOrDefault(argMap, "--eta-max", etaMax);
            etaStep = getDoubleOrDefault(argMap, "--eta-step", etaStep);
        }
        seedBase = getLongOrDefault(argMap, "--seed-base", seedBase);
        runsPerEta = getIntOrDefault(argMap, "--runs-per-eta", runsPerEta);
        density = getDoubleOrDefault(argMap, "--density", density);
        if (runsPerEta < 1) {
            throw new IllegalArgumentException("--runs-per-eta must be >= 1");
        }
        if (density <= 0.0) {
            throw new IllegalArgumentException("--density must be > 0");
        }

        Path binDir = resolveBinPath();
        Files.createDirectories(binDir);

        Path outCsv = binDir.resolve("polarization_vs_step_by_eta.csv");

        double L = 10.0;
        long N = Math.round(Math.pow(L, 2) * density);

        double rc = 1.0;
        double dt = 1.0;
        boolean periodicBorders = true;
        double velocityModule = 0.03;

        // En tp2-sim (AutomataOffLattice) minParticleRadius=maxParticleRadius=0 => radios y props en 0.
        double minParticleRadius = 0.0;
        double maxParticleRadius = 0.0;
        double property = 0.0;

        List<Double> etas = hasEtas
                ? parseEtaList(argMap.get("--etas"))
                : generateEtaValues(etaMin, etaMax, etaStep);
        int etaCount = etas.size();

        System.out.println("Running PolarizationVsStepByEtaRunner with parameters:");
        System.out.printf(Locale.US, "  steps=%d%n", steps);
        if (hasEtas) {
            System.out.printf(Locale.US, "  etas=%s%n", etas);
        } else {
            System.out.printf(Locale.US, "  eta-min=%.6g, eta-max=%.6g, eta-step=%.6g%n", etaMin, etaMax, etaStep);
            System.out.printf(Locale.US, "  generated-etas=%s%n", etas);
        }
        System.out.printf(Locale.US, "  density=%.6g%n", density);
        System.out.printf(Locale.US, "  runs-per-eta=%d%n", runsPerEta);
        System.out.printf(Locale.US, "  seed-base=%d%n", seedBase);
        System.out.printf(Locale.US, "  leader=%s%n", leaderType);

        // Simulamos cada eta por separado (misma grilla, distintas semillas).
        // Guardamos una serie por (eta, run).
        double[][][] vaSeries = new double[etaCount][runsPerEta][(int) steps];

        for (int etaIdx = 0; etaIdx < etaCount; etaIdx++) {
            double eta = etas.get(etaIdx);
            for (int runIdx = 0; runIdx < runsPerEta; runIdx++) {
                long seed = seedBase + etaIdx * 1_000_003L + runIdx * 10_000_019L;
                java.util.Random rng = new java.util.Random(seed);

                List<Particle> particles = generateInitialParticles(
                        N, L, periodicBorders, velocityModule, minParticleRadius, maxParticleRadius, property, rng
                );

                CircularLeaderConfig circularLeaderConfig = null;
                if (leaderType == LeaderType.CIRCULAR_TRAJECTORY) {
                    // Enunciado: radio R=5, centro (L/2, L/2). Tangencial speed ~ velocityModule.
                    double R = 5.0;
                    double cx = L / 2.0;
                    double cy = L / 2.0;
                    double omega = velocityModule / R;
                    double phi0 = rng.nextDouble() * 2.0 * Math.PI;

                    // Override de lider id=1 con posicion/velocidad consistente con phi0.
                    for (int i = 0; i < particles.size(); i++) {
                        Particle p = particles.get(i);
                        if (p.id() == LEADER_ID) {
                            double x = cx + R * Math.cos(phi0);
                            double y = cy + R * Math.sin(phi0);
                            if (periodicBorders) {
                                x = modPos(x, L);
                                y = modPos(y, L);
                            }
                            double vx = -velocityModule * Math.sin(phi0);
                            double vy = velocityModule * Math.cos(phi0);
                            particles.set(i, new Particle(p.id(), x, y, vx, vy, p.radius(), p.property()));
                            break;
                        }
                    }

                    circularLeaderConfig = new CircularLeaderConfig(cx, cy, R, phi0, omega);
                }

                List<Particle> current = particles;
                for (int s = 0; s < steps; s++) {
                    vaSeries[etaIdx][runIdx][s] = computePolarization(current);
                    double time = s * dt;
                    current = advanceOneStep(
                            current, L, rc, velocityModule, dt, eta, periodicBorders, leaderType, circularLeaderConfig, time, rng
                    );
                }

                System.out.printf(Locale.US, "eta=%.3f run=%d/%d done%n", eta, runIdx + 1, runsPerEta);
            }
        }

        // Escribir CSV ancho (wide):
        // header: step, eta_<value>_run_<idx>, ...
        try (BufferedWriter w = new BufferedWriter(new FileWriter(outCsv.toFile()))) {
            w.write("step");
            for (int etaIdx = 0; etaIdx < etaCount; etaIdx++) {
                for (int runIdx = 0; runIdx < runsPerEta; runIdx++) {
                    // Use eta/run in the column name so plotting can group same-eta series by color.
                    w.write(String.format(Locale.US, ",eta_%.6g_run_%d", etas.get(etaIdx), runIdx + 1));
                }
            }
            w.newLine();

            for (int s = 0; s < steps; s++) {
                w.write(Integer.toString(s));
                for (int etaIdx = 0; etaIdx < etaCount; etaIdx++) {
                    for (int runIdx = 0; runIdx < runsPerEta; runIdx++) {
                        w.write(String.format(Locale.US, ",%.12f", vaSeries[etaIdx][runIdx][s]));
                    }
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
        System.out.printf(Locale.US, "runs-per-eta=%d%n", runsPerEta);
    }

    private static List<Double> generateEtaValues(double etaMin, double etaMax, double etaStep) {
        if (etaStep <= 0.0) {
            throw new IllegalArgumentException("--eta-step must be > 0");
        }
        if (etaMax < etaMin) {
            throw new IllegalArgumentException("--eta-max must be >= --eta-min");
        }
        int count = (int) Math.round((etaMax - etaMin) / etaStep);
        List<Double> etas = new ArrayList<>(count + 1);
        for (int i = 0; i <= count; i++) {
            etas.add(etaMin + i * etaStep);
        }
        etas.sort(Comparator.naturalOrder());
        return etas;
    }

    private static List<Double> parseEtaList(String etaListRaw) {
        if (etaListRaw == null || etaListRaw.isBlank()) {
            throw new IllegalArgumentException("--etas must be a non-empty comma-separated list");
        }

        List<Double> etas = java.util.Arrays.stream(etaListRaw.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .map(Double::parseDouble)
                .sorted()
                .collect(Collectors.toList());
        if (etas.isEmpty()) {
            throw new IllegalArgumentException("--etas must include at least one eta value");
        }
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
                                                 LeaderType leaderType,
                                                 CircularLeaderConfig circularLeaderConfig,
                                                 double time,
                                                 java.util.Random rng) {
        // Vecinos del estado actual (t).
        CellIndexMethodNeighborFinder cim = new CellIndexMethodNeighborFinder(particles.size(), L, rc, periodicBorders, particles);
        cim.findNeighbors();
        Map<Particle, List<Particle>> neighborMap = cim.particleNeighborsMap;

        List<Particle> next = new ArrayList<>(particles.size());

        for (Particle p : particles) {
            if (p.id() == LEADER_ID && leaderType == LeaderType.CIRCULAR_TRAJECTORY) {
                // Actualizacion deterministica circular: usa theta(t+dt) como en AutomataOffLattice.
                double nextTime = time + dt;
                double theta = circularLeaderConfig.phi0 + circularLeaderConfig.omega * nextTime;

                double newX = circularLeaderConfig.cx + circularLeaderConfig.radius * Math.cos(theta);
                double newY = circularLeaderConfig.cy + circularLeaderConfig.radius * Math.sin(theta);

                double vx = -velocityModule * Math.sin(theta);
                double vy = velocityModule * Math.cos(theta);

                if (periodicBorders) {
                    newX = modPos(newX, L);
                    newY = modPos(newY, L);
                } else {
                    newX = Math.max(0.0, Math.min(L, newX));
                    newY = Math.max(0.0, Math.min(L, newY));
                }

                next.add(new Particle(p.id(), newX, newY, vx, vy, p.radius(), p.property()));
                continue;
            }

            if (p.id() == LEADER_ID && leaderType == LeaderType.FIXED_DIRECTION) {
                // Direccion fija: el lider no se alinea con vecinos, sigue su direccion constante.
                double newTheta = angle(p);
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
                continue;
            }

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

    private static int getIntOrDefault(Map<String, String> map, String key, int defaultValue) {
        String v = map.get(key);
        if (v == null) return defaultValue;
        return Integer.parseInt(v);
    }
}

