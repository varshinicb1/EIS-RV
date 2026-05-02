/**
 * Crystal 3D Visualization Module
 * ================================
 * Uses 3Dmol.js for WebGL-based crystal structure rendering
 */

class Crystal3DViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.viewer = null;
        this.currentStructure = null;
        this.init();
    }

    init() {
        // Initialize 3Dmol viewer
        this.viewer = $3Dmol.createViewer(this.container, {
            backgroundColor: '#0a0e1a',
            antialias: true
        });
        
        // Set default view
        this.viewer.setView([0, 0, 0], 50);
        this.viewer.render();
    }

    /**
     * Load crystal structure from NVIDIA API or fallback
     */
    async loadStructure(formula) {
        try {
            // Try NVIDIA API first
            const response = await fetch('/api/nvidia/crystal', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({formula: formula})
            });

            if (response.ok) {
                const data = await response.json();
                this.renderStructure(data);
                return data;
            } else {
                // Fallback to simple structure
                this.renderFallbackStructure(formula);
            }
        } catch (error) {
            console.error('Crystal loading error:', error);
            this.renderFallbackStructure(formula);
        }
    }

    /**
     * Render crystal structure
     */
    renderStructure(structure) {
        this.viewer.clear();
        this.currentStructure = structure;

        // Parse atoms
        const atoms = structure.atoms || [];
        const lattice = structure.lattice || {a: 5, b: 5, c: 5};

        // Create unit cell
        this.drawUnitCell(lattice);

        // Add atoms
        atoms.forEach(atom => {
            const x = atom.x * lattice.a;
            const y = atom.y * lattice.b;
            const z = atom.z * lattice.c;

            this.viewer.addSphere({
                center: {x, y, z},
                radius: this.getAtomicRadius(atom.element),
                color: this.getAtomicColor(atom.element),
                alpha: 0.9
            });

            // Add label
            this.viewer.addLabel(atom.element, {
                position: {x, y, z},
                fontSize: 12,
                fontColor: 'white',
                backgroundColor: 'rgba(0,0,0,0.5)',
                backgroundOpacity: 0.5
            });
        });

        // Add bonds (simple distance-based)
        this.addBonds(atoms, lattice);

        // Render
        this.viewer.zoomTo();
        this.viewer.render();
    }

    /**
     * Draw unit cell box
     */
    drawUnitCell(lattice) {
        const {a, b, c} = lattice;
        const corners = [
            [0, 0, 0], [a, 0, 0], [a, b, 0], [0, b, 0],
            [0, 0, c], [a, 0, c], [a, b, c], [0, b, c]
        ];

        const edges = [
            [0,1], [1,2], [2,3], [3,0],  // bottom
            [4,5], [5,6], [6,7], [7,4],  // top
            [0,4], [1,5], [2,6], [3,7]   // vertical
        ];

        edges.forEach(([i, j]) => {
            this.viewer.addCylinder({
                start: {x: corners[i][0], y: corners[i][1], z: corners[i][2]},
                end: {x: corners[j][0], y: corners[j][1], z: corners[j][2]},
                radius: 0.05,
                color: 'gray',
                alpha: 0.5
            });
        });
    }

    /**
     * Add bonds between atoms
     */
    addBonds(atoms, lattice) {
        const maxBondLength = 2.5; // Angstroms

        for (let i = 0; i < atoms.length; i++) {
            for (let j = i + 1; j < atoms.length; j++) {
                const atom1 = atoms[i];
                const atom2 = atoms[j];

                const x1 = atom1.x * lattice.a;
                const y1 = atom1.y * lattice.b;
                const z1 = atom1.z * lattice.c;

                const x2 = atom2.x * lattice.a;
                const y2 = atom2.y * lattice.b;
                const z2 = atom2.z * lattice.c;

                const distance = Math.sqrt(
                    (x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2
                );

                if (distance < maxBondLength) {
                    this.viewer.addCylinder({
                        start: {x: x1, y: y1, z: z1},
                        end: {x: x2, y: y2, z: z2},
                        radius: 0.1,
                        color: 'white',
                        alpha: 0.7
                    });
                }
            }
        }
    }

    /**
     * Fallback structure for common materials
     */
    renderFallbackStructure(formula) {
        // Simple cubic lattice
        const structure = {
            formula: formula,
            lattice: {a: 5, b: 5, c: 5},
            atoms: [
                {element: formula.substring(0, 2).trim(), x: 0.0, y: 0.0, z: 0.0},
                {element: formula.substring(0, 2).trim(), x: 0.5, y: 0.5, z: 0.0},
                {element: formula.substring(0, 2).trim(), x: 0.5, y: 0.0, z: 0.5},
                {element: formula.substring(0, 2).trim(), x: 0.0, y: 0.5, z: 0.5}
            ],
            source: 'fallback'
        };

        this.renderStructure(structure);
    }

    /**
     * Get atomic radius (van der Waals)
     */
    getAtomicRadius(element) {
        const radii = {
            'H': 1.2, 'C': 1.7, 'N': 1.55, 'O': 1.52, 'F': 1.47,
            'P': 1.8, 'S': 1.8, 'Cl': 1.75, 'Li': 1.82, 'Na': 2.27,
            'K': 2.75, 'Mg': 1.73, 'Ca': 2.31, 'Fe': 2.0, 'Mn': 2.0,
            'Co': 2.0, 'Ni': 1.63, 'Cu': 1.4, 'Zn': 1.39
        };
        return radii[element] || 1.5;
    }

    /**
     * Get CPK atomic colors
     */
    getAtomicColor(element) {
        const colors = {
            'H': '#FFFFFF', 'C': '#909090', 'N': '#3050F8', 'O': '#FF0D0D',
            'F': '#90E050', 'P': '#FF8000', 'S': '#FFFF30', 'Cl': '#1FF01F',
            'Li': '#CC80FF', 'Na': '#AB5CF2', 'K': '#8F40D4', 'Mg': '#8AFF00',
            'Ca': '#3DFF00', 'Fe': '#E06633', 'Mn': '#9C7AC7', 'Co': '#F090A0',
            'Ni': '#50D050', 'Cu': '#C88033', 'Zn': '#7D80B0'
        };
        return colors[element] || '#FF1493';
    }

    /**
     * Rotate structure
     */
    rotate(axis, angle) {
        this.viewer.rotate(angle, axis);
        this.viewer.render();
    }

    /**
     * Reset view
     */
    resetView() {
        this.viewer.zoomTo();
        this.viewer.render();
    }

    /**
     * Export as image
     */
    exportImage() {
        return this.viewer.pngURI();
    }

    /**
     * Set rendering style
     */
    setStyle(style) {
        // style: 'sphere', 'stick', 'cartoon', 'surface'
        this.viewer.setStyle({}, {[style]: {}});
        this.viewer.render();
    }
}

// Export for use in main app
window.Crystal3DViewer = Crystal3DViewer;
