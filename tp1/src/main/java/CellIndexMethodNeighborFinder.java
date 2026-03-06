import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;



public class CellIndexMethodNeighborFinder {
    private long particleCount;             // N
    private double environmentSideLength;   // L
    private int cellAmount;                 // M
    private double cellSideLength;          // L/M
    private double detectionRadius;         // rc
    private boolean periodicBorders;

    private List<Particle>[][] environmentGrid;

    Map<Particle, List<Particle>> particleNeighborsMap;

    public CellIndexMethodNeighborFinder(final long N, final double L, final int M, final double rc, boolean periodicBorders, List<Particle> particles) {
        checkParameters(L, M, rc, particles);

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
            int p_i = (int) (p.x() / cellSideLength);
            int p_j = (int) (p.y() / cellSideLength);

            int[][] indexOffsets = {{0,0},{0,-1},{1,-1},{1,0},{1,1}};   // Solo recorremos los cuatro cuadrantes a la derecha

            for (int[] offsets : indexOffsets) {
                List<Particle> neighbors = particlesInCell(p_i + offsets[0], p_j + offsets[1]);
                if(neighbors == null) {
                    continue;
                }
                for(Particle neighbor : neighbors) {
                    if(p ==  neighbor) {
                        continue;
                    }
                    if(p.distanceTo(neighbor) < detectionRadius) {
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
            int i = (int) (p.x() / cellSideLength);
            int j = (int) (p.y() / cellSideLength);
            if(environmentGrid[i][j] == null) {
                environmentGrid[i][j] = new ArrayList<>();
            }
            environmentGrid[i][j].add(new Particle(p.x(), p.y(), p.radius()));
        }
    }

    private void checkParameters(final double L, final int M, final double rc, final List<Particle> particles) {
        double largest= 0, secondLargest = 0;
        for(Particle p : particles) {
            if(p.radius() > secondLargest) {
                secondLargest = p.radius();
            }
            if(secondLargest > largest) {
                double tmp = largest;
                largest = secondLargest;
                secondLargest = tmp;
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
}