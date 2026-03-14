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

    /** When withLeader is true, particle with id 1 is the leader (not affected by others, follows its own path). */
    private static final long LEADER_ID = 1L;

    public static void main(String[] args) throws IOException {
        long start = System.nanoTime();
        boolean withLeader = false;
        for (String arg : args) {
            if ("--withLeader".equals(arg)) {
                withLeader = true;
                break;
            }
        }
        long maxFrames = DEFAULT_MAX_FRAMES;
        for (String arg : args) {
            try {
                maxFrames = Long.parseLong(arg);
                break;
            } catch (NumberFormatException ignored) {
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

        runVicsekSimulation(particles, L, rc, velocityModule, DEFAULT_DT, DEFAULT_NOISE, steps, periodicBorders, withLeader, binDir);
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
                                            boolean withLeader,
                                            Path binDir) throws IOException {
        Path framesDir = binDir.resolve("frames");
        recreateDir(framesDir);

        List<Particle> current = new ArrayList<>(initialParticles);
        for (long step = 0; step < steps; step++) {
            double time = step * dt;
            exportFrame(framesDir, step, time, current);
            current = advanceOneStep(current, L, rc, velocityModule, dt, eta, periodicBorders, withLeader);
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
                                                 boolean withLeader) {

        CellIndexMethodNeighborFinder cim = new CellIndexMethodNeighborFinder(particles.size(), L, rc, periodicBorders, particles);
        cim.findNeighbors();

        Map<Particle, List<Particle>> neighborMap = cim.particleNeighborsMap;

        List<Particle> next = new ArrayList<>(particles.size());

        for (Particle p : particles) {
            double newTheta;
            if (withLeader && p.id() == LEADER_ID) {
                // Leader: not affected by others, follows its own path (current direction, no noise).
                newTheta = angle(p);
            } else {
                List<Particle> neighbors = neighborMap.getOrDefault(p, Collections.emptyList());

                double sumSin = Math.sin(angle(p));
                double sumCos = Math.cos(angle(p));

                for (Particle n : neighbors) {
                    sumSin += Math.sin(angle(n));
                    sumCos += Math.cos(angle(n));
                }

                double avgTheta = Math.atan2(sumSin, sumCos);
                double noise = (ThreadLocalRandom.current().nextDouble() - 0.5) * eta; // Uniform in [-eta/2, eta/2]
                newTheta = avgTheta + noise;
            }

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
