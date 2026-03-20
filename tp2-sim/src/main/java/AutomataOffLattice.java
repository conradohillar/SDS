import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

public class AutomataOffLattice {
    private static final String BIN_PATH = resolveBinPath();
    private static final double DEFAULT_DT = 1.0;

    private static String resolveBinPath() {
        String fromEnv = System.getenv("TP2_BIN_PATH");
        if (fromEnv != null && !fromEnv.isEmpty()) {
            return fromEnv;
        }
        return Paths.get(System.getProperty("user.dir")).resolve("tp2-bin").toAbsolutePath().normalize().toString();
    }
    private static final double DEFAULT_NOISE = 0.5;
    private static final long DEFAULT_MAX_FRAMES = 1000L;

    /** The "leader" particle is always the one with id 1. */
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
        long start = System.nanoTime();
        LeaderType leaderType = LeaderType.NONE;
        double eta = DEFAULT_NOISE;
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            if ("--leader-fixed".equals(arg)) {
                leaderType = LeaderType.FIXED_DIRECTION;
                continue;
            } else if ("--leader-circular".equals(arg)) {
                leaderType = LeaderType.CIRCULAR_TRAJECTORY;
                continue;
            } else if ("--eta".equals(arg)) {
                if (i + 1 >= args.length) {
                    throw new IllegalArgumentException("Missing value for --eta");
                }
                eta = Double.parseDouble(args[i + 1]);
                i++; // consume value
                continue;
            } else if (arg.startsWith("--eta=")) {
                String value = arg.substring("--eta=".length());
                eta = Double.parseDouble(value);
                continue;
            }
        }
        long maxFrames = DEFAULT_MAX_FRAMES;
        boolean maxFramesProvided = false;
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            if ("--max-frames".equals(arg)) {
                if (i + 1 >= args.length) {
                    throw new IllegalArgumentException("Missing value for --max-frames");
                }
                maxFrames = Long.parseLong(args[i + 1]);
                maxFramesProvided = true;
                i++; // consume value
            } else if (arg.startsWith("--max-frames=")) {
                String value = arg.substring("--max-frames=".length());
                maxFrames = Long.parseLong(value);
                maxFramesProvided = true;
            }
        }
        // Backwards-compatible fallback: if no explicit --max-frames was provided,
        // keep supporting "first numeric arg == maxFrames" from earlier versions.
        if (!maxFramesProvided) {
            for (String arg : args) {
                try {
                    maxFrames = Long.parseLong(arg);
                    break;
                } catch (NumberFormatException ignored) {
                }
            }
        }
        long steps = maxFrames > 0 ? maxFrames - 1 : 0;

        double L = 10.0;
        int cellDensity = 4;
        long N = (long) Math.pow(L,2) * cellDensity;
        double rc = 1.0;
        double minParticleRadius = 0.0;
        double maxParticleRadius = 0.0;
        boolean periodicBorders = true;
        double velocityModule = 0.03;

        Path binDir = Paths.get(BIN_PATH);
        ParticlePlotGenerator particlePlotGenerator = new ParticlePlotGenerator(
                N, L, minParticleRadius, maxParticleRadius, periodicBorders, velocityModule, binDir
        );
        particlePlotGenerator.exportFiles();
        String staticPath = particlePlotGenerator.binFile("static.txt").toString();
        String dynamicPath = particlePlotGenerator.binFile("dynamic.txt").toString();
        StaticData sd = InputParser.parseStatic(staticPath);
        DynamicData dd = InputParser.parseDynamic(dynamicPath);
        List<Particle> particles = InputParser.buildParticles(sd, dd);

        CircularLeaderConfig circularLeaderConfig = null;
        if (leaderType == LeaderType.CIRCULAR_TRAJECTORY) {
            // Enunciado: radio R=5, centro de libre elección (elegimos (L/2, L/2) para simplificar).
            double radius = 5.0;
            double cx = L / 2.0;
            double cy = L / 2.0;

            // Elegimos omega para que la velocidad tangencial sea "similar" a la del resto:
            // tangential speed v_t = omega * R ~ velocityModule. Aquí es igual.
            double omega = velocityModule / radius;
            double phi0 = ThreadLocalRandom.current().nextDouble(0.0, 2.0 * Math.PI);

            for (int i = 0; i < particles.size(); i++) {
                Particle p = particles.get(i);
                if (p.id() == LEADER_ID) {
                    double x = cx + radius * Math.cos(phi0);
                    double y = cy + radius * Math.sin(phi0);
                    if (periodicBorders) {
                        x = ((x % L) + L) % L;
                        y = ((y % L) + L) % L;
                    }
                    // Tangential velocity for position (cx + R cos(phi), cy + R sin(phi)).
                    double vx = -velocityModule * Math.sin(phi0);
                    double vy = velocityModule * Math.cos(phi0);
                    particles.set(i, new Particle(p.id(), x, y, vx, vy, p.radius(), p.property()));
                    break;
                }
            }

            circularLeaderConfig = new CircularLeaderConfig(cx, cy, radius, phi0, omega);
        }

        runVicsekSimulation(particles, L, rc, velocityModule, DEFAULT_DT, eta, steps, periodicBorders, leaderType,
                circularLeaderConfig, binDir);
        long end = System.nanoTime();
        System.out.printf("Rendered %d frames in %.3f seconds\n", maxFrames, (end - start) / 1000000000.0);
    }

    private static void runVicsekSimulation(List<Particle> initialParticles,
                                            double L,
                                            double rc,
                                            double velocityModule,
                                            double dt,
                                            double eta,
                                            long steps,
                                            boolean periodicBorders,
                                            LeaderType leaderType,
                                            CircularLeaderConfig circularLeaderConfig,
                                            Path binDir) throws IOException {
        Path framesDir = binDir.resolve("frames");
        recreateDir(framesDir);

        List<Particle> current = new ArrayList<>(initialParticles);
        for (long step = 0; step < steps; step++) {
            double time = step * dt;
            exportFrame(framesDir, step, time, current);
            current = advanceOneStep(current, L, rc, velocityModule, dt, eta, periodicBorders, leaderType, circularLeaderConfig, time);
        }
        exportFrame(framesDir, steps, steps * dt, current);
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
                                                 double time) {

        CellIndexMethodNeighborFinder cim = new CellIndexMethodNeighborFinder(particles.size(), L, rc, periodicBorders, particles);
        cim.findNeighbors();

        Map<Particle, List<Particle>> neighborMap = cim.particleNeighborsMap;

        List<Particle> next = new ArrayList<>(particles.size());

        for (Particle p : particles) {
            if (p.id() == LEADER_ID && leaderType == LeaderType.CIRCULAR_TRAJECTORY) {
                // Circular leader: position and velocity are fully pre-defined (no noise, no alignment).
                // Leader influences others through its velocity included in the neighbor alignment.
                double nextTime = time + dt;
                double theta = circularLeaderConfig.phi0 + circularLeaderConfig.omega * nextTime;

                double newX = circularLeaderConfig.cx + circularLeaderConfig.radius * Math.cos(theta);
                double newY = circularLeaderConfig.cy + circularLeaderConfig.radius * Math.sin(theta);

                // Tangential velocity (speed = velocityModule).
                double vx = -velocityModule * Math.sin(theta);
                double vy = velocityModule * Math.cos(theta);

                if (periodicBorders) {
                    newX = ((newX % L) + L) % L;
                    newY = ((newY % L) + L) % L;
                } else {
                    newX = Math.max(0.0, Math.min(L, newX));
                    newY = Math.max(0.0, Math.min(L, newY));
                }

                next.add(new Particle(p.id(), newX, newY, vx, vy, p.radius(), p.property()));
                continue;
            }

            if (p.id() == LEADER_ID && leaderType == LeaderType.FIXED_DIRECTION) {
                // Fixed direction leader: not affected by others, follows its own constant direction.
                double newTheta = angle(p);
                double vx = velocityModule * Math.cos(newTheta);
                double vy = velocityModule * Math.sin(newTheta);

                double newX = p.x() + vx * dt;
                double newY = p.y() + vy * dt;

                if (periodicBorders) {
                    newX = ((newX % L) + L) % L;
                    newY = ((newY % L) + L) % L;
                } else {
                    newX = Math.max(0.0, Math.min(L, newX));
                    newY = Math.max(0.0, Math.min(L, newY));
                }

                next.add(new Particle(p.id(), newX, newY, vx, vy, p.radius(), p.property()));
                continue;
            }

            // Standard Vicsek update for all other particles (including id 1 when leaderType == NONE).
            List<Particle> neighbors = neighborMap.getOrDefault(p, Collections.emptyList());

            double sumSin = Math.sin(angle(p));
            double sumCos = Math.cos(angle(p));

            for (Particle n : neighbors) {
                sumSin += Math.sin(angle(n));
                sumCos += Math.cos(angle(n));
            }

            double avgTheta = Math.atan2(sumSin, sumCos);
            double noise = (ThreadLocalRandom.current().nextDouble() - 0.5) * eta; // Uniform in [-eta/2, eta/2]
            double newTheta = avgTheta + noise;

            double vx = velocityModule * Math.cos(newTheta);
            double vy = velocityModule * Math.sin(newTheta);

            double newX = p.x() + vx * dt;
            double newY = p.y() + vy * dt;

            if (periodicBorders) {
                newX = ((newX % L) + L) % L;
                newY = ((newY % L) + L) % L;
            } else {
                newX = Math.max(0.0, Math.min(L, newX));
                newY = Math.max(0.0, Math.min(L, newY));
            }

            next.add(new Particle(p.id(), newX, newY, vx, vy, p.radius(), p.property()));
        }

        return next;
    }

    private static void exportFrame(Path framesDir, long frameIndex, double time, List<Particle> particles) throws IOException {
        String filename = String.format("frame_%05d.txt", frameIndex);
        Path tmp = framesDir.resolve(filename + ".tmp");
        Path out = framesDir.resolve(filename);

        try (var writer = Files.newBufferedWriter(tmp)) {
            writer.write(String.format("%.6f", time));
            writer.newLine();
            for (Particle p : particles) {
                writer.write(String.format("%.6f\t%.6f\t%.6f\t%.6f", p.x(), p.y(), p.vx(), p.vy()));
                writer.newLine();
            }
        }
        Files.move(tmp, out, java.nio.file.StandardCopyOption.ATOMIC_MOVE, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
    }

    private static double angle(Particle p) {
        return Math.atan2(p.vy(), p.vx());
    }

    private static void recreateDir(Path dir) throws IOException {
        if (Files.exists(dir)) {
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(dir)) {
                for (Path p : stream) {
                    Files.deleteIfExists(p);
                }
            }
        } else {
            Files.createDirectories(dir);
        }
    }
}
