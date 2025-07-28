// graph_renderer.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("graph_renderer.js loaded and DOMContentLoaded.");

    // Find all graph containers
    var graphContainers = document.querySelectorAll('.vis-graph-container');

    graphContainers.forEach(function(container) {
        var graphId = container.id;
        var nodesJson = container.getAttribute('data-nodes');
        var edgesJson = container.getAttribute('data-edges');

        console.log(`Initializing graph for container: ${graphId}`);
        console.log("Nodes JSON (from data-attribute):", nodesJson);
        console.log("Edges JSON (from data-attribute):", edgesJson);

        if (!nodesJson || !edgesJson) {
            console.warn(`No graph data found for container ${graphId}. Skipping.`);
            return;
        }

        try {
            var nodesData = JSON.parse(nodesJson);
            var edgesData = JSON.parse(edgesJson);

            if (typeof vis === 'undefined' || !vis.DataSet) {
                console.error("vis.js library not loaded. Cannot render graph.");
                container.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">Error: vis.js library not loaded.</p>';
                return;
            }

            var nodes = new vis.DataSet(nodesData);
            var edges = new vis.DataSet(edgesData);

            var data = {
                nodes: nodes,
                edges: edges
            };

            var options = {
                nodes: {
                    shape: 'circle',
                    font: {
                        size: 14
                    },
                    color: {
                        background: '#97C2FC',
                        border: '#2B7CE9',
                        highlight: {
                            background: '#D2E5FF',
                            border: '#2B7CE9'
                        }
                    }
                },
                edges: {
                    font: {
                        size: 12,
                        align: 'middle'
                    },
                    color: {
                        color: '#848484'
                    },
                    smooth: {
                        enabled: true,
                        type: "dynamic"
                    }
                },
                physics: {
                    stabilization: true,
                    barnesHut: {
                        gravitationalConstant: -2000,
                        centralGravity: 0.3,
                        springLength: 150,
                        springConstant: 0.04
                    }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 200
                }
            };

            console.log(`Creating vis.Network instance for ${graphId}...`);
            var network = new vis.Network(container, data, options);
            console.log(`vis.Network instance created successfully for ${graphId}.`);

            network.on("click", function(params) {
                if (params.nodes.length > 0) {
                    var nodeId = params.nodes[0];
                    console.log('Clicked node:', nodeId);
                }
            });

        } catch (error) {
            console.error(`Error creating network graph for ${graphId}:`, error);
            container.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">Error loading graph visualization: ' + error.message + '</p>';
        }
    });
});
