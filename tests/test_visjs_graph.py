#!/usr/bin/env python3
"""
A minimal test program for the Vis.js graph visualization feature.
This program creates a simple adjacency graph, generates the HTML visualization,
and saves it to a file that can be opened in a browser.
"""

import json
import random

def generate_visjs_graph(adjacency_graph):
    """
    Generates HTML and JavaScript code for a vis.js graph.
    
    Args:
        adjacency_graph (dict): The adjacency graph data.
        
    Returns:
        str: A string containing the HTML and JavaScript code to embed the graph.
    """
    nodes = []
    edges = []

    for node_id, connections in adjacency_graph.items():
        nodes.append(f"{{id: '{node_id}', label: '{node_id}'}}")
        for connection in connections:
            if connection['similarity'] > 0.2:
                edges.append(f"{{from: '{node_id}', to: '{connection['other_id']}', label: '{connection['similarity']:.2f}', arrows: 'to'}}")

    nodes_str = ",\n".join(nodes)
    edges_str = ",\n".join(edges)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hypothesis Similarity Graph Test</title>
        <style>
            body, html {{
                height: 100%;
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
                /* Ensure html and body take full height */
                height: 100%; 
            }}
            .container {{
                width: 100%;
                height: 100%; /* Back to percentage height */
                display: flex;
                flex-direction: column;
                /* Add overflow hidden just in case */
                overflow: hidden; 
            }}
            #mynetwork {{
                /* Explicit height instead of flex: 1 */
                height: calc(100% - 100px); /* Example: Subtract approx height of info div */
                width: 100%; 
                border: 1px solid #ccc;
                position: relative; /* Needed for canvas positioning */
            }}
            .info {{
                padding: 10px;
                background-color: #f5f5f5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="info">
                <h2>Hypothesis Similarity Graph Test</h2>
                <p>
                    <b>How to read the graph:</b><br>
                    - Each node (circle) represents a hypothesis.<br>
                    - Lines (edges) between nodes indicate similarity between hypotheses.<br>
                    - The number on each edge represents the similarity score. Higher numbers mean greater similarity.<br>
                    - Only similarities above 0.2 are shown.<br>
                </p>
            </div>
            <div id="mynetwork"></div>
        </div>
        
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <script type="text/javascript">
            var nodes = new vis.DataSet([
                {nodes_str} // Restore dynamic nodes
            ]);
            var edges = new vis.DataSet([
                {edges_str} // Restore dynamic edges
            ]);
            var container = document.getElementById('mynetwork');
            var data = {{
                nodes: nodes,
                edges: edges
            }};
            // Restore original options
            var options = {{
                nodes: {{
                    shape: 'circle',
                    font: {{
                        size: 14
                    }}
                }},
                edges: {{
                    font: {{
                        size: 12,
                        align: 'middle'
                    }},
                    smooth: {{
                        enabled: true,
                        type: "dynamic",
                    }},
                }},
                physics: {{ // Restore physics
                    stabilization: true,
                    barnesHut: {{
                        gravitationalConstant: -2000,
                        centralGravity: 0.3,
                        springLength: 150,
                        springConstant: 0.04,
                    }}
                }}
            }};
            
            // Wait for the DOM to be fully loaded before initializing the graph
            document.addEventListener('DOMContentLoaded', function () {{
                // Remove try/catch and console logs from minimal example
                var network = new vis.Network(container, data, options);
            }});
        </script>
    </body>
    </html>
    """

def create_test_adjacency_graph(num_nodes=5):
    """
    Creates a test adjacency graph with random similarity scores.
    
    Args:
        num_nodes (int): Number of nodes to create.
        
    Returns:
        dict: An adjacency graph dictionary.
    """
    adjacency = {}
    
    # Create node IDs (H1, H2, etc.)
    node_ids = [f"H{i+1}" for i in range(num_nodes)]
    
    # Create connections between nodes with random similarity scores
    for i, node_id in enumerate(node_ids):
        adjacency[node_id] = []
        for j, other_id in enumerate(node_ids):
            if i != j:  # Don't connect a node to itself
                # Generate a random similarity score between 0.1 and 0.9
                similarity = round(random.uniform(0.1, 0.9), 2)
                adjacency[node_id].append({
                    "other_id": other_id,
                    "similarity": similarity
                })
    
    return adjacency

def main():
    # Create a test adjacency graph
    adjacency_graph = create_test_adjacency_graph(num_nodes=7)
    
    # Print the adjacency graph for reference
    print("Adjacency Graph:")
    print(json.dumps(adjacency_graph, indent=2))
    
    # Generate the HTML visualization
    html = generate_visjs_graph(adjacency_graph)
    
    # Save the HTML to a file
    output_file = "test_graph.html"
    with open(output_file, "w") as f:
        f.write(html)
    
    print(f"\nGraph visualization saved to {output_file}")
    print(f"Open this file in a web browser to view the graph.")

if __name__ == "__main__":
    main()
