import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;



public class CellIndexMethodNeighborFinder {
    private long particleCount;                     // N
    private final double environmentSideLength;     // L
    private final int cellAmount;                   // M
    private final double cellSideLength;            // L/M
    private final double detectionRadius;           // rc
    private final boolean periodicBorders;

    private final List<Particle>[][] environmentGrid;
    private final Map<Particle, List<Particle>> particleNeighborsMap;

    public CellIndexMethodNeighborFinder(final long N, final double L, final int M, final double rc, boolean periodicBorders, List<Particle> particles) {
        checkParameters(N, L, M, rc, particles);

        this.particleCount = N;
        this.environmentSideLength = L;
        this.cellAmount = M;
        this.cellSideLength = L/M;
        this.detectionRadius = rc;
        this.periodicBorders = periodicBorders;

        this.particleNeighborsMap = new HashMap<>();
        for (Particle p : particles) {
            particleNeighborsMap.put(p, new ArrayList<>());
        }

        environmentGrid = new ArrayList[M][M];
        fillEnvironmentGrid(particles);
    }

    public Map<Particle, List<Particle>> findNeighbors() {
        for (Particle p : particleNeighborsMap.keySet()) {
            int p_i = Math.min((int) (p.x() / cellSideLength), cellAmount - 1);
            int p_j = Math.min((int) (p.y() / cellSideLength), cellAmount - 1);

            int[][] indexOffsets = {{0,0},{0,-1},{1,-1},{1,0},{1,1}};   // Recorremos solo las celdas necesarias para no repetir pares

            for (int[] offsets : indexOffsets) {
                List<Particle> neighbors = particlesInCell(p_i + offsets[0], p_j + offsets[1]);
                if(neighbors == null) {
                    continue;
                }
                for(Particle neighbor : neighbors) {
                    if(p.equals(neighbor) || p.id() > neighbor.id()) {
                        continue;
                    }
                    if(areNeighbors(p, neighbor)) {
                        particleNeighborsMap.get(neighbor).add(p);
                        particleNeighborsMap.get(p).add(neighbor);
                    }
                }
            }
        }
        return particleNeighborsMap;
    }

    private void fillEnvironmentGrid(final List<Particle> particles) {
        for (Particle p : particles) {
            int i = Math.min((int) (p.x() / cellSideLength), cellAmount - 1);
            int j = Math.min((int) (p.y() / cellSideLength), cellAmount - 1);
            if(environmentGrid[i][j] == null) {
                environmentGrid[i][j] = new ArrayList<>();
            }
            environmentGrid[i][j].add(p);
        }
    }

    private void checkParameters(final long N, final double L, final int M, final double rc, final List<Particle> particles) {
        if (particles.size() != N) {
            throw new IllegalArgumentException("Particle count does not match N");
        }

        double largest= 0, secondLargest = 0;
        for(Particle p : particles) {
            double r = p.radius();
            if(r > largest) {
                secondLargest = largest;
                largest = r;
            } else if(r > secondLargest) {
                secondLargest = r;
            }
        }
        if(L/M <= rc + largest + secondLargest) {
            throw new RuntimeException("L/M out of range (lesser than rc + largest particles' radius)");
        }
    }

    private List<Particle> particlesInCell(int i, int j) {
        int real_i = i, real_j = j;
        if(periodicBorders) {
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
        if(periodicBorders) {
            dx -= environmentSideLength * Math.round(dx / environmentSideLength);
            dy -= environmentSideLength * Math.round(dy / environmentSideLength);
        }
        double dist = Math.sqrt(dx*dx + dy*dy);
        return dist <= detectionRadius + a.radius() + b.radius();
    }
}