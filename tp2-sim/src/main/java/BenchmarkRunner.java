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
 * Cumple el enunciado:
 * - 10 corridas por tipo de lider (ninguno, fijo, circular) y por valor de eta
 * - 500 steps
 * - descarta primeros 250 steps (transitorio) y promedia polarizacion en el resto
 * - calcula media y desviacion estandar entre corridas
 *
 * Output:
 * - tp2-bin/benchmark_polarization_summary.csv
 * - tp2-bin/benchmark_polarization_per_run.csv
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
        private final int runsPerSetting;
        private final double etaMin;
        private final double etaMax;
        private final double etaStep;

        private Params(long maxFrames, long discardFrames, int runsPerSetting, double etaMin, double etaMax, double etaStep) {
            this.maxFrames = maxFrames;
            this.discardFrames = discardFrames;
            this.runsPerSetting = runsPerSetting;
            this.etaMin = etaMin;
            this.etaMax = etaMax;
            this.etaStep = etaStep;
        }
    }

    public static void main(String[] args) throws IOException {
        Locale.setDefault(Locale.US);

        // Defaults alineados al pedido del usuario/enunciado.
        Params params = new Params(
                500L,   // 500 steps
                250L,   // descartar primeras 250
                10,     // 10 corridas
                0.0,    // eta desde 0
                5.0,    // eta hasta 5
                0.25    // salto 0.25
        );

        Map<String, String> argMap = parseArgs(args);
        params = new Params(
                getLongOrDefault(argMap, "--max-frames", params.maxFrames),
                getLongOrDefault(argMap, "--discard-frames", params.discardFrames),
                getIntOrDefault(argMap, "--runs-per-eta", params.runsPerSetting),
                getDoubleOrDefault(argMap, "--eta-min", params.etaMin),
                getDoubleOrDefault(argMap, "--eta-max", params.etaMax),
                getDoubleOrDefault(argMap, "--eta-step", params.etaStep)
        );

        Path binDir = resolveBinPath();
        Files.createDirectories(binDir);

        Path perRunCsv = binDir.resolve("benchmark_polarization_per_run.csv");
        Path summaryCsv = binDir.resolve("benchmark_polarization_summary.csv");

        long totalStartNs = System.nanoTime();

        // Ejecutar y guardar polarizacion media por corrida.
        try (BufferedWriter perRunWriter = new BufferedWriter(new FileWriter(perRunCsv.toFile()));
             BufferedWriter summaryWriter = new BufferedWriter(new FileWriter(summaryCsv.toFile()))) {

            perRunWriter.write("eta,leader_type,run_index,polarization_mean");
            perRunWriter.newLine();

            summaryWriter.write("eta,leader_type,mean_polarization,std_polarization");
            summaryWriter.newLine();

            for (double eta : generateEtaValues(params.etaMin, params.etaMax, params.etaStep)) {
                for (LeaderType leaderType : List.of(LeaderType.NONE, LeaderType.FIXED_DIRECTION, LeaderType.CIRCULAR_TRAJECTORY)) {
                    long comboStartNs = System.nanoTime();
                    double[] runMeans = new double[params.runsPerSetting];

                    for (int runIndex = 0; runIndex < params.runsPerSetting; runIndex++) {
                        double runMean = runOneSimulationAndMeasure(
                                eta, leaderType, params.maxFrames, params.discardFrames
                        );
                        runMeans[runIndex] = runMean;
                        perRunWriter.write(String.format(Locale.US, "%.8f,%s,%d,%.12f",
                                eta, leaderTypeKey(leaderType), runIndex, runMean));
                        perRunWriter.newLine();
                    }

                    double mean = mean(runMeans);
                    double std = stdSample(runMeans, mean);
                    summaryWriter.write(String.format(Locale.US, "%.8f,%s,%.12f,%.12f",
                            eta, leaderTypeKey(leaderType), mean, std));
                    summaryWriter.newLine();

                    perRunWriter.flush();
                    summaryWriter.flush();

                    long comboElapsedNs = System.nanoTime() - comboStartNs;
                    System.out.printf(
                            Locale.US,
                            "eta=%.3f leader=%s finished in %.3f s%n",
                            eta,
                            leaderTypeKey(leaderType),
                            comboElapsedNs / 1_000_000_000.0
                    );
                }
            }
        }

        long totalElapsedNs = System.nanoTime() - totalStartNs;
        System.out.printf(Locale.US, "TOTAL benchmark time: %.3f s%n", totalElapsedNs / 1_000_000_000.0);
    }

    private static double runOneSimulationAndMeasure(double eta,
                                                      LeaderType leaderType,
                                                      long maxFrames,
                                                      long discardFrames) {
        // Configuracion fija segun AutomataOffLattice / enunciado.
        double L = 10.0;
        int cellDensity = 4;
        long N = (long) Math.pow(L, 2) * cellDensity; // 400

        double rc = 1.0;
        double dt = 1.0;
        boolean periodicBorders = true;
        double velocityModule = 0.03;

        // En AutomataOffLattice: minParticleRadius=maxParticleRadius=0 => radios y props en 0.
        double minParticleRadius = 0.0;
        double maxParticleRadius = 0.0;
        double property = 0.0;

        // Seed por corrida (para que cada run tenga configuracion distinta).
        // Usamos ThreadLocalRandom para no traer java.util.Random y reducir code duplication.
        long seed = ThreadLocalRandom.current().nextLong();
        java.util.Random rng = new java.util.Random(seed);

        List<Particle> particles = generateInitialParticles(N, L, periodicBorders, velocityModule, minParticleRadius, maxParticleRadius, property, rng);

        CircularLeaderConfig circularLeaderConfig = null;
        if (leaderType == LeaderType.CIRCULAR_TRAJECTORY) {
            // Enunciado: radio R=5; centro de libre elección. Elegimos (L/2, L/2) como en AutomataOffLattice.
            double R = 5.0;
            double cx = L / 2.0;
            double cy = L / 2.0;
            double omega = velocityModule / R; // tangencial ~ v0
            double phi0 = rng.nextDouble() * 2.0 * Math.PI;

            // Override de lider id=1 con la posicion/velocidad consistente con phi0.
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

        long measuredCount = 0L;
        double polSum = 0.0;

        List<Particle> current = particles;
        for (long step = 0; step < maxFrames; step++) {
            double pol = computePolarization(current);
            if (step >= discardFrames) {
                polSum += pol;
                measuredCount++;
            }

            double time = step * dt;
            current = advanceOneStep(current, L, rc, velocityModule, dt, eta, periodicBorders, leaderType, circularLeaderConfig, time, rng);
        }

        return measuredCount > 0 ? polSum / measuredCount : 0.0;
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

    private static double mean(double[] values) {
        double sum = 0.0;
        for (double v : values) {
            sum += v;
        }
        return sum / values.length;
    }

    private static double stdSample(double[] values, double mean) {
        if (values.length <= 1) return 0.0;
        double sum = 0.0;
        for (double v : values) {
            double d = v - mean;
            sum += d * d;
        }
        return Math.sqrt(sum / (values.length - 1));
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

