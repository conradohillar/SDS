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
import java.util.TreeMap;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Bench de polarizacion vs eta para el Vicsek off-lattice (TP2).
 *
 * Una unica simulacion de 5000 steps por cada (eta, leader_type).
 * Descarta los primeros pasos (transitorio) y calcula media y desvio
 * estandar de la polarizacion sobre los steps restantes (estado estacionario).
 *
 * Output:
 * - tp2-bin/benchmark_polarization_summary.csv   (eta, leader_type, mean, std)
 * - tp2-bin/benchmark_polarization_per_step.csv   (eta, leader_type, step, polarization)
 */
public class BenchmarkRunner {
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
        private final double phi0;
        private final double omega;

        private CircularLeaderConfig(double cx, double cy, double radius, double phi0, double omega) {
            this.cx = cx;
            this.cy = cy;
            this.radius = radius;
            this.phi0 = phi0;
            this.omega = omega;
        }
    }

    private static final class Params {
        private final long maxFrames;
        private final long discardFrames;
        private final double etaMin;
        private final double etaMax;
        private final double etaStep;
        private final int density;
        private final List<LeaderType> leaderTypes;

        private Params(long maxFrames, long discardFrames, double etaMin, double etaMax, double etaStep,
                        int density, List<LeaderType> leaderTypes) {
            this.maxFrames = maxFrames;
            this.discardFrames = discardFrames;
            this.etaMin = etaMin;
            this.etaMax = etaMax;
            this.etaStep = etaStep;
            this.density = density;
            this.leaderTypes = leaderTypes;
        }
    }

    private static List<LeaderType> parseLeaderTypes(String value) {
        List<LeaderType> types = new ArrayList<>();
        for (String token : value.split(",")) {
            switch (token.trim().toLowerCase(Locale.US)) {
                case "none" -> types.add(LeaderType.NONE);
                case "fixed" -> types.add(LeaderType.FIXED_DIRECTION);
                case "circular" -> types.add(LeaderType.CIRCULAR_TRAJECTORY);
                default -> throw new IllegalArgumentException("Unknown leader type: " + token.trim()
                        + ". Valid values: none, fixed, circular");
            }
        }
        if (types.isEmpty()) {
            throw new IllegalArgumentException("--leader requires at least one type (none, fixed, circular)");
        }
        return types;
    }

    public static void main(String[] args) throws IOException {
        Locale.setDefault(Locale.US);

        Map<String, String> argMap = parseArgs(args);

        List<LeaderType> leaderTypes = argMap.containsKey("--leader")
                ? parseLeaderTypes(argMap.get("--leader"))
                : List.of(LeaderType.NONE, LeaderType.FIXED_DIRECTION, LeaderType.CIRCULAR_TRAJECTORY);

        Params params = new Params(
                getLongOrDefault(argMap, "--max-frames", 5000L),
                getLongOrDefault(argMap, "--discard-frames", 1000L),
                getDoubleOrDefault(argMap, "--eta-min", 0.0),
                getDoubleOrDefault(argMap, "--eta-max", 5.0),
                getDoubleOrDefault(argMap, "--eta-step", 0.25),
                getIntOrDefault(argMap, "--density", 4),
                leaderTypes
        );

        System.out.printf(Locale.US,
                "Config: steps=%d discard=%d eta=[%.2f..%.2f step=%.2f] density=%d leaders=%s%n",
                params.maxFrames, params.discardFrames,
                params.etaMin, params.etaMax, params.etaStep,
                params.density,
                params.leaderTypes.stream().map(BenchmarkRunner::leaderTypeKey).toList());

        Path binDir = resolveBinPath();
        Files.createDirectories(binDir);

        Path perStepCsv = binDir.resolve("benchmark_polarization_per_step.csv");
        Path summaryCsv = binDir.resolve("benchmark_polarization_summary.csv");

        long totalStartNs = System.nanoTime();

        try (BufferedWriter perStepWriter = new BufferedWriter(new FileWriter(perStepCsv.toFile()));
             BufferedWriter summaryWriter = new BufferedWriter(new FileWriter(summaryCsv.toFile()))) {

            perStepWriter.write("eta,leader_type,step,polarization");
            perStepWriter.newLine();

            summaryWriter.write("eta,leader_type,mean_polarization,std_polarization");
            summaryWriter.newLine();

            for (double eta : generateEtaValues(params.etaMin, params.etaMax, params.etaStep)) {
                for (LeaderType leaderType : params.leaderTypes) {
                    long comboStartNs = System.nanoTime();

                    double[] polPerStep = runOneSimulation(eta, leaderType, params.maxFrames, params.density);

                    for (int step = 0; step < polPerStep.length; step++) {
                        perStepWriter.write(String.format(Locale.US, "%.8f,%s,%d,%.12f",
                                eta, leaderTypeKey(leaderType), step, polPerStep[step]));
                        perStepWriter.newLine();
                    }

                    int steadyStart = (int) Math.min(params.discardFrames, polPerStep.length);
                    int steadyCount = polPerStep.length - steadyStart;

                    double mean = 0.0;
                    double std = 0.0;
                    if (steadyCount > 0) {
                        double sum = 0.0;
                        for (int i = steadyStart; i < polPerStep.length; i++) {
                            sum += polPerStep[i];
                        }
                        mean = sum / steadyCount;

                        if (steadyCount > 1) {
                            double sumSq = 0.0;
                            for (int i = steadyStart; i < polPerStep.length; i++) {
                                double d = polPerStep[i] - mean;
                                sumSq += d * d;
                            }
                            std = Math.sqrt(sumSq / (steadyCount - 1));
                        }
                    }

                    summaryWriter.write(String.format(Locale.US, "%.8f,%s,%.12f,%.12f",
                            eta, leaderTypeKey(leaderType), mean, std));
                    summaryWriter.newLine();

                    perStepWriter.flush();
                    summaryWriter.flush();

                    long comboElapsedNs = System.nanoTime() - comboStartNs;
                    System.out.printf(
                            Locale.US,
                            "eta=%.3f leader=%-8s  mean=%.6f std=%.6f  (%.3f s)%n",
                            eta,
                            leaderTypeKey(leaderType),
                            mean,
                            std,
                            comboElapsedNs / 1_000_000_000.0
                    );
                }
            }
        }

        long totalElapsedNs = System.nanoTime() - totalStartNs;
        System.out.printf(Locale.US, "TOTAL benchmark time: %.3f s%n", totalElapsedNs / 1_000_000_000.0);
    }

    /**
     * Corre una unica simulacion de {@code maxFrames} steps y devuelve
     * la polarizacion medida en cada step (array de longitud maxFrames).
     */
    private static double[] runOneSimulation(double eta,
                                              LeaderType leaderType,
                                              long maxFrames,
                                              int density) {
        double L = 10.0;
        long N = (long) (L * L) * density;

        double rc = 1.0;
        double dt = 1.0;
        boolean periodicBorders = true;
        double velocityModule = 0.03;

        double minParticleRadius = 0.0;
        double maxParticleRadius = 0.0;
        double property = 0.0;

        long seed = ThreadLocalRandom.current().nextLong();
        java.util.Random rng = new java.util.Random(seed);

        List<Particle> particles = generateInitialParticles(N, L, periodicBorders, velocityModule, minParticleRadius, maxParticleRadius, property, rng);

        CircularLeaderConfig circularLeaderConfig = null;
        if (leaderType == LeaderType.CIRCULAR_TRAJECTORY) {
            double R = 5.0;
            double cx = L / 2.0;
            double cy = L / 2.0;
            double omega = velocityModule / R;
            double phi0 = rng.nextDouble() * 2.0 * Math.PI;

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

        int totalSteps = (int) maxFrames;
        double[] polPerStep = new double[totalSteps];

        List<Particle> current = particles;
        for (int step = 0; step < totalSteps; step++) {
            polPerStep[step] = computePolarization(current);
            double time = step * dt;
            current = advanceOneStep(current, L, rc, velocityModule, dt, eta, periodicBorders, leaderType, circularLeaderConfig, time, rng);
        }

        return polPerStep;
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
        java.util.Map<Particle, List<Particle>> neighborMap = cim.particleNeighborsMap;

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
                // Direccion fija: sin alineacion con vecinos, sin ruido.
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
            double noise = (rng.nextDouble() - 0.5) * eta; // Uniform in [-eta/2, eta/2]
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

    private static String leaderTypeKey(LeaderType leaderType) {
        return switch (leaderType) {
            case NONE -> "none";
            case FIXED_DIRECTION -> "fixed";
            case CIRCULAR_TRAJECTORY -> "circular";
        };
    }

    private static List<Double> generateEtaValues(double etaMin, double etaMax, double etaStep) {
        // Generamos por índice para evitar drift por floating point.
        int count = (int) Math.round((etaMax - etaMin) / etaStep);
        List<Double> etas = new ArrayList<>(count + 1);
        for (int i = 0; i <= count; i++) {
            etas.add(etaMin + i * etaStep);
        }
        etas.sort(Comparator.naturalOrder());
        return etas;
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
        // El resto se ignora.
        TreeMap<String, String> map = new TreeMap<>();
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

    private static int getIntOrDefault(Map<String, String> map, String key, int defaultValue) {
        String v = map.get(key);
        if (v == null) return defaultValue;
        return Integer.parseInt(v);
    }

    private static double getDoubleOrDefault(Map<String, String> map, String key, double defaultValue) {
        String v = map.get(key);
        if (v == null) return defaultValue;
        return Double.parseDouble(v);
    }
}

