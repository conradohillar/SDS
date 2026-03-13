import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.util.*;

public class CellIndexMethodNeighborFinder {
    private long particleCount; // N
    private final double environmentSideLength; // L
    private final int cellAmount; // M
    private final double cellSideLength; // L/M
    private final double detectionRadius; // rc
    private final boolean periodicBorders;

    private final List<Particle>[][] environmentGrid;

    Map<Particle, List<Particle>> particleNeighborsMap;

    public CellIndexMethodNeighborFinder(final long N, final double L, final int M, final double rc,
            boolean periodicBorders, List<Particle> particles) {
        checkParameters(N, particles);

        this.particleCount = N;
        this.environmentSideLength = L;
        this.detectionRadius = rc;
        this.periodicBorders = periodicBorders;

        this.particleNeighborsMap = new HashMap<>();
        for (Particle p : particles) {
            particleNeighborsMap.put(p, new ArrayList<>());
        }
        int newM;
        if (M == 0) {
            newM = getMaxMValue(L, rc, particles);
        } else {
            newM = M;
        }
        this.cellSideLength = L / newM;
        environmentGrid = new ArrayList[newM][newM];
        this.cellAmount = newM;
        fillEnvironmentGrid(particles);


    }

    public void findNeighbors() {
        for (Particle p : particleNeighborsMap.keySet()) {
            int p_i = Math.min((int) (p.x() / cellSideLength), cellAmount - 1);
            int p_j = Math.min((int) (p.y() / cellSideLength), cellAmount - 1);

            int[][] indexOffsets = { { 0, 0 }, { 0, -1 }, { 1, -1 }, { 1, 0 }, { 1, 1 } };

            for (int[] offsets : indexOffsets) {
                boolean sameCell = (offsets[0] == 0 && offsets[1] == 0);
                List<Particle> neighbors = particlesInCell(p_i + offsets[0], p_j + offsets[1]);
                if (neighbors == null) {
                    continue;
                }
                for (Particle neighbor : neighbors) {
                    if (p.equals(neighbor)) {
                        continue;
                    }
                    if (sameCell && p.id() > neighbor.id()) {
                        continue;
                    }
                    if (areNeighbors(p, neighbor)) {
                        particleNeighborsMap.get(neighbor).add(p);
                        particleNeighborsMap.get(p).add(neighbor);
                    }
                }
            }
        }
    }

    public void findNeighborsBruteForce() {
        for (Particle p1 : particleNeighborsMap.keySet()) {
            for (Particle p2 : particleNeighborsMap.keySet()) {
                if (p1.equals(p2)) {
                    continue;
                }
                if (areNeighbors(p1, p2)) {
                    particleNeighborsMap.get(p1).add(p2);
                }
            }
        }
    }

    private void fillEnvironmentGrid(final List<Particle> particles) {
        for (Particle p : particles) {
            int i = Math.min((int) (p.x() / cellSideLength), cellAmount - 1);
            int j = Math.min((int) (p.y() / cellSideLength), cellAmount - 1);
            if (environmentGrid[i][j] == null) {
                environmentGrid[i][j] = new ArrayList<>();
            }
            environmentGrid[i][j].add(p);
        }
    }

    private static int getMaxMValue(final double L, final double rc, final List<Particle> particles) {
        double largest = 0, secondLargest = 0;
        for (Particle p : particles) {
            double r = p.radius();
            if (r > largest) {
                secondLargest = largest;
                largest = r;
            } else if (r > secondLargest) {
                secondLargest = r;
            }
        }
        return (int)(L / (rc + largest + secondLargest));
    }

    private void checkParameters(final long N, final List<Particle> particles) {
        if (particles.size() != N) {
            throw new IllegalArgumentException("Particle count does not match N");
        }
    }

    private List<Particle> particlesInCell(int i, int j) {
        int real_i = i, real_j = j;
        if (periodicBorders) {
            real_i = (i + cellAmount) % cellAmount;
            real_j = (j + cellAmount) % cellAmount;
        } else if (i < 0 || i >= cellAmount || j < 0 || j >= cellAmount) {
            return null;
        }
        return environmentGrid[real_i][real_j];
    }

    private boolean areNeighbors(Particle a, Particle b) {
        double dx = b.x() - a.x();
        double dy = b.y() - a.y();
        if (periodicBorders) {
            dx -= environmentSideLength * Math.round(dx / environmentSideLength);
            dy -= environmentSideLength * Math.round(dy / environmentSideLength);
        }
        double dist = Math.sqrt(dx * dx + dy * dy);
        return dist <= detectionRadius + a.radius() + b.radius();
    }

    public void printOutput() {
        try (BufferedWriter writer = new BufferedWriter(
                new FileWriter(ParticlePlotGenerator.BIN_PATH + "neighbors.txt"))) {
            for (Map.Entry<Particle, List<Particle>> entry : particleNeighborsMap.entrySet()) {
                Particle p = entry.getKey();
                List<Particle> neighbors = entry.getValue();
                writer.write(String.format("%d", p.id()));
                for (Particle neighbor : neighbors) {
                    writer.write(String.format(",%d", neighbor.id()));
                }
                writer.newLine();
            }
        } catch (IOException e) {
            throw new RuntimeException("Failed to export static.txt", e);
        }

    }

    public static void main(String[] args) throws IOException {
        if (true) {

            long N = 500;
            double L = 20.0;
            double rc = 1.0;
            int M = 0; // Si M = 0, calcula el M óptimo
            double minParticleRadius = 0.23;
            double maxParticleRadius = 0.26;
            boolean periodicBorders = true;

            ParticlePlotGenerator particlePlotGenerator = new ParticlePlotGenerator(N, L, minParticleRadius,
                    maxParticleRadius, periodicBorders);
            particlePlotGenerator.exportFiles();
            String staticPath = ParticlePlotGenerator.BIN_PATH + "static.txt";
            String dynamicPath = ParticlePlotGenerator.BIN_PATH + "dynamic.txt";
            StaticData sd = InputParser.parseStatic(staticPath);
            DynamicData dd = InputParser.parseDynamic(dynamicPath);
            List<Particle> particles = InputParser.buildParticles(sd, dd);
            CellIndexMethodNeighborFinder cim = new CellIndexMethodNeighborFinder(N, L, M, rc, periodicBorders,
                    particles);
            long time = System.currentTimeMillis();
            cim.findNeighborsBruteForce();
            long endTime = System.currentTimeMillis();
            System.out.printf("Time to find neighbors: %.3f s",  (endTime - time) / 1000.0);
            cim.printOutput();
        } else {
            throw new RuntimeException("Insufficient arguments.");
        }

    }

}