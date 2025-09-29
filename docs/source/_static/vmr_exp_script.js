// Global variables to store the data and original data
let data;
let originalData;

// Event listener to handle file upload
Dropzone.options.myDropzone = {
    url: "#", // Prevent Dropzone from sending a POST request
    paramName: "vmr_schedule", // The name that will be used to transfer the file
    maxFilesize: 25, // MB
    maxFiles: 1, // Allow only one file at a time
    acceptedFiles: ".json", // Accept only JSON files
    dictDefaultMessage:
        "Drag and drop or click to upload an exported VM Resource Schedule.", // Default message
    init: function () {
        this.on("addedfile", function (file) {
            // Remove any existing files
            if (this.files.length > 1) {
                this.removeFile(this.files[0]); // Remove the first file
            }
            this.emit("thumbnail", file, "logo_no_text.png");

            // Customize the file preview
            const filePreview = Dropzone.createElement(`
                <div class="dz-preview dz-file-preview">
                    <div class="dz-details">
                        <div class="dz-filename"><strong data-dz-name="">${file.name}</strong></div>
                        <div class="dz-size" data-dz-size=""><strong>${(file.size / 1024).toFixed(2)}</strong> KB</div>
                    </div>
                    <div class="dz-image">
                        <img data-dz-thumbnail src="logo_no_text.png" style="width: 100px; height: 100px; object-fit: cover;" />
                    </div>
                </div>
            `);

            // Append the custom preview to the Dropzone
            this.previewsContainer.appendChild(filePreview);

            // Create a new FileReader
            const reader = new FileReader();

            // Event listener for when the file is loaded
            reader.onload = function (event) {
                try {
                    // Parse the file data as JSON
                    data = JSON.parse(event.target.result);
                    originalData = JSON.parse(event.target.result);
                    loadScheduleEntries(originalData);

                    // Update the graph
                    updateGraph();
                } catch (error) {
                    if (error instanceof SyntaxError) {
                        // Catch only JSON parsing errors
                        showSnackbar(
                            "Error parsing the file. Please ensure it is a valid JSON file.",
                        );
                    } else {
                        // Log other errors and show a generic message
                        console.error("An error occurred:", error);
                        showSnackbar("An unexpected error occurred. Please try again.");
                    }
                }
            };

            // Read the uploaded file as text
            reader.readAsText(file);
        });

        // Prevent Dropzone from sending the file to the server
        this.on("sending", function (file, xhr, formData) {
            // Prevent the default behavior
            xhr.abort();
            // Manually trigger the complete event
            this.emit("complete", file);
        });
    },
};

// Event listener to apply filters
document.getElementById("applyFilters").addEventListener("click", () => {
    // Get the filter values
    const vmName = document.getElementById("vmFilter").value.trim().toLowerCase();
    const startTimeInput = document.getElementById("startTime").value;
    const startTime =
        startTimeInput !== "" && !isNaN(parseInt(startTimeInput))
            ? parseInt(startTimeInput)
            : null;
    const endTimeInput = document.getElementById("endTime").value;
    const endTime =
        endTimeInput !== "" && !isNaN(parseInt(endTimeInput))
            ? parseInt(endTimeInput)
            : null;

    // Filter the data
    const filteredData = filterSchedule(data, vmName, startTime, endTime);

    // Load the schedule entries
    loadScheduleEntries(filteredData);

    // Update the current filters section with chips
    const currentFiltersContainer = document.getElementById("current-filters");
    currentFiltersContainer.innerHTML = ""; // Clear previous filters

    if (vmName) {
        const vmChip = document.createElement("div");
        vmChip.className = "filter-chip";
        vmChip.innerHTML = `<strong>VM Name:</strong> <span class="chip-value">${vmName}</span> <span class="remove-chip" onclick="removeFilter('vmName')">&times;</span>`;
        currentFiltersContainer.appendChild(vmChip);
    }

    if (startTime !== null) {
        const startChip = document.createElement("div");
        startChip.className = "filter-chip";
        startChip.innerHTML = `<strong>Start Time:</strong> <span class="chip-value">${startTime}</span> <span class="remove-chip" onclick="removeFilter('startTime')">&times;</span>`;
        currentFiltersContainer.appendChild(startChip);
    }

    if (endTime !== null) {
        const endChip = document.createElement("div");
        endChip.className = "filter-chip";
        endChip.innerHTML = `<strong>End Time:</strong> <span class="chip-value">${endTime}</span> <span class="remove-chip" onclick="removeFilter('endTime')">&times;</span>`;
        currentFiltersContainer.appendChild(endChip);
    }
});

function showSnackbar(message) {
    const snackbar = document.getElementById("snackbar");
    snackbar.textContent = message; // Set the message
    snackbar.className = "snackbar show"; // Add the "show" class to display it

    // After 3 seconds, remove the show class from snackbar
    setTimeout(function () {
        snackbar.className = snackbar.className.replace("show", ""); // Remove the "show" class
    }, 3000);
}

// Function to remove a filter
function removeFilter(filterType) {
    if (filterType === "vmName") {
        document.getElementById("vmFilter").value = ""; // Clear the input
    } else if (filterType === "startTime") {
        document.getElementById("startTime").value = ""; // Clear the input
    } else if (filterType === "endTime") {
        document.getElementById("endTime").value = ""; // Clear the input
    }

    // Reapply filters to update the display
    applyFilters(); // Call your existing function to reapply filters
}

// Function to apply filters (to be called in removeFilter)
function applyFilters() {
    // Trigger the click event of the apply filters button
    document.getElementById("applyFilters").click();
}

function loadScheduleEntries(data) {
    // Get the table body element
    const tbody = document.getElementById("scheduleBody");
    tbody.innerHTML = "";

    // Get the time keys
    const timeKeys = Object.keys(data).sort((a, b) => parseInt(a) - parseInt(b));

    // Get the table head element
    const thead = document.querySelector("#scheduleTable thead");

    // Create the table header
    if (thead.children.length === 0) {
        const headerRow = document.createElement("tr");
        headerRow.innerHTML = "<th>VM Name</th>";
        timeKeys.forEach((time) => {
            const th = document.createElement("th");
            th.textContent = time;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
    } else {
        const headerRow = thead.querySelector("tr");
        headerRow.innerHTML = "<th>VM Name</th>";
        timeKeys.forEach((time) => {
            const th = document.createElement("th");
            th.textContent = time;
            headerRow.appendChild(th);
        });
    }

    // Get the unique VM names
    const vmNames = new Set();
    timeKeys.forEach((time) => {
        data[time].forEach((entry) => {
            vmNames.add(entry.name);
        });
    });

    // Create the table rows
    vmNames.forEach((vmName) => {
        const row = document.createElement("tr");

        const vmCell = document.createElement("td");
        vmCell.textContent = vmName;
        vmCell.classList.add("vm-name");
        row.appendChild(vmCell);

        timeKeys.forEach((time) => {
            const cell = document.createElement("td");

            const entries = data[time].filter((entry) => entry.name === vmName);

            if (entries.length > 0) {
                entries.forEach((entry, index) => {
                    const link = document.createElement("md-outlined-button");
                    link.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px"><path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z"/></svg>&nbsp;${entry.executable}`; // Use the info icon
                    link.style.cursor = "pointer";

                    // Add event listener to display details
                    link.addEventListener("click", function (event) {
                        event.preventDefault();
                        showDetails(vmName, time, entry);
                    });

                    if (index > 0) {
                        const br = document.createElement("br");
                        cell.appendChild(br);
                    }

                    cell.appendChild(link);
                });
            } else {
                cell.textContent = "";
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });
}

function showDetails(vmName, time, entry) {
    const modal = document.getElementById("detailsModal");
    const modalContent = document.getElementById("modalDetailsContent");
    const modalHeader = modal.querySelector(".modal-header"); // Select the time element
    modalContent.innerHTML = "";

    // Update the time dynamically
    modalHeader.innerHTML = `
        <div class="modal-header-content">
            <span class="vm-name">${vmName}</span>
            <span class="time">Execution Time: ${time}</span>
        </div>
    `;

    // Display the command in a visually appealing way
    const commandDiv = document.createElement("div");
    commandDiv.className = "command";
    commandDiv.innerHTML = `
        <strong>Command:</strong><br>
        <span class="command-executable">${entry.executable}</span>&nbsp; 
        <span class="command-arguments">${entry.arguments}</span>
    `;
    modalContent.appendChild(commandDiv);

    // Create details for the selected entry
    const detailsDiv = document.createElement("div");
    detailsDiv.className = "entry-detail";
    detailsDiv.innerHTML = `
        <strong>Executable:</strong> <span class="command-executable">${entry.executable}</span><br>
        <strong>Arguments:</strong> <span class="command-arguments">${entry.arguments}</span><br>
        <strong>Pause:</strong> <span class="pause">${entry.pause !== null && entry.pause !== undefined ? entry.pause : "N/A"}</span><br>
    `;
    modalContent.appendChild(detailsDiv);

    // Check if there are files associated with the entry
    if (entry.data && entry.data.length > 0) {
        // Display all files associated with the entry
        const filesDiv = document.createElement("div");
        filesDiv.className = "files-list";
        filesDiv.innerHTML = "<strong>Files:</strong><br>";

        entry.data.forEach((file, index) => {
            const executableStatus = file.executable
                ? `<span class="status-icon" title="Executable"><i class="fas fa-check-circle" style="color: var(--md-sys-color-success);"></i> Yes</span>`
                : `<span class="status-icon" title="Not Executable"><i class="fas fa-times-circle" style="color: var(--md-sys-color-error);"></i> No</span>`;

            const fileDiv = document.createElement("div");
            fileDiv.className = "file-detail";
            fileDiv.innerHTML = `
                <strong>Filename:</strong> <span class="location">${file.location}</span><br>
                <strong>Executable:</strong> <span class="executable">${executableStatus}</span><br>
                ${
                    file.content
                        ? `
                <div class="code-block">
                    <div class="code-header">
                        <span class="code-title">File Content</span>
                    </div>
                    <pre><code>${file.content}</code></pre>
                </div>
                `
                        : ""
                }
                <br>
            `;
            filesDiv.appendChild(fileDiv);
        });

        modalContent.appendChild(filesDiv); // Append filesDiv to modalContent
    }
    // After appending the fileDiv, call highlight.js to process the new content
    hljs.highlightAll();

    // Show the modal
    modal.style.display = "block";
}

let initialTransform; // Variable to store the initial transformation
function updateGraph() {
    // Get the SVG element
    const svg = d3.select("#graph");
    svg.selectAll("*").remove();

    // Create a group for the graph to apply zoom
    const graphGroup = svg.append("g");

    // Set up zoom behavior
    const zoom = d3
        .zoom()
        .scaleExtent([0.05, 5]) // Set the zoom scale limits
        .on("zoom", (event) => {
            graphGroup.attr("transform", event.transform); // Apply the zoom transformation
        });

    svg.call(zoom); // Apply the zoom behavior to the SVG

    // Get the graph data
    const graphData = [];

    Object.keys(data).forEach((time) => {
        data[time].forEach((entry) => {
            graphData.push({
                time: parseInt(time),
                name: entry.name,
                executable: entry.executable,
                arguments: entry.arguments,
            });
        });
    });

    // Get the unique server names
    const servers = [...new Set(graphData.map((d) => d.name))];

    // Create the server nodes
    const serverNodes = [];
    servers.forEach((server, index) => {
        serverNodes.push({ name: server, x: 100, y: index * 100 + 50 }); // Fixed x position, vertical spacing
    });

    // Create the time nodes and edges
    const timeNodes = [];
    const edges = []; // Array to store edges

    // Create a map to track the time nodes for each server
    const serverTimeMap = new Map();

    Object.keys(data).forEach((time) => {
        const timeNum = parseInt(time);
        servers.forEach((server) => {
            const entries = data[time].filter((e) => e.name === server); // Use filter to get all matching entries
            entries.forEach((entry) => {
                // Iterate over all matching entries
                const node = {
                    name: entry.executable,
                    time: timeNum,
                    server: server,
                    x: 0,
                    y: 0,
                }; // Placeholder positions
                timeNodes.push(node);

                // Add to the server's time map
                if (!serverTimeMap.has(server)) {
                    serverTimeMap.set(server, []);
                }
                serverTimeMap.get(server).push(node);
            });
        });
    });

    // Create edges based on server and time nodes
    serverNodes.forEach((serverNode) => {
        const serverTimeNodes = serverTimeMap.get(serverNode.name) || [];

        // Sort time nodes for the server by time (more negative means earlier)
        serverTimeNodes.sort((a, b) => a.time - b.time);

        // Create edges from the server node to the first time node
        if (serverTimeNodes.length > 0) {
            const firstTimeNode = serverTimeNodes[0];
            edges.push({ source: serverNode, target: firstTimeNode });

            // Create edges based on server and time nodes
            const uniqueTimes = Array.from(
                new Set(serverTimeNodes.map((node) => node.time)),
            ).sort((a, b) => a - b);

            for (let i = 0; i < uniqueTimes.length - 1; i++) {
                const currentTime = uniqueTimes[i];
                const nextTime = uniqueTimes[i + 1];

                // Get all nodes for the current time and the next time
                const currentTimeNodes = serverTimeNodes.filter(
                    (node) => node.time === currentTime,
                );
                const nextTimeNodes = serverTimeNodes.filter(
                    (node) => node.time === nextTime,
                );

                // Create edges from all current time nodes to all next time nodes
                currentTimeNodes.forEach((sourceNode) => {
                    nextTimeNodes.forEach((targetNode) => {
                        edges.push({ source: sourceNode, target: targetNode });
                    });
                });
            }
        }
    });

    // Prepare the tangled tree data
    const levels = convertToTangledTreeData(serverNodes, timeNodes, edges);

    // Now we have the proper data, call the renderChart function
    const tangleLayout = constructTangleLayout(levels);
    const background_color = "white";
    const color = d3.scaleOrdinal(d3.schemeDark2);

    // Create the SVG element for the tangled tree visualization
    const width = Math.min(tangleLayout.layout.width, 1200); // Set a maximum width
    const height = Math.min(tangleLayout.layout.height, 800); // Set a maximum height

    svg.attr("width", 1200)
        .attr("height", 800)
        .style("background-color", background_color);

    // Center the graph initially
    const centerX = width / 2;
    const centerY = height / 2;
    const translateX = centerX - tangleLayout.layout.width / 2;
    const translateY = centerY - tangleLayout.layout.height / 2;

    graphGroup.attr("transform", `translate(${translateX}, ${translateY})`);

    // Add styles
    svg.append("style").text(`
        text {
            font-family: sans-serif;
            font-size: 10px;
        }
        .node {
            stroke-linecap: round;
        }
        .link {
            fill: none;
        }
    `);

    // Draw links
    tangleLayout.bundles.forEach((b, i) => {
        let d = b.links
            .map(
                (l) => `
            M${l.xt} ${l.yt}
            L${l.xb - l.c1} ${l.yt}
            A${l.c1} ${l.c1} 90 0 ${l.sweepFlag1} ${l.xb} ${l.arc1Point}
            L${l.xb} ${l.arc2Point}
            A${l.c2} ${l.c2} 90 0 ${l.sweepFlag2} ${l.xb + l.c2} ${l.ys}
            L${l.xs} ${l.ys}`,
            )
            .join("");
        // Draw the background link (for hover effects)
        graphGroup
            .append("path")
            .attr("class", "link")
            .attr("d", d)
            .attr("stroke", background_color) // Background color for hover effect
            .attr("stroke-width", 5);

        // Draw the actual link with color
        graphGroup
            .append("path")
            .attr("class", "link")
            .attr("d", d)
            .attr("stroke", color(i)) // Apply color based on the index
            .attr("stroke-width", 2);
    });

    // Draw nodes
    tangleLayout.nodes.forEach((n) => {
        graphGroup
            .append("path")
            .attr("class", "selectable node")
            .attr("data-id", n.id)
            .attr("stroke", "black")
            .attr("stroke-width", 8)
            .attr("d", `M${n.x} ${n.y - n.height / 2} L${n.x} ${n.y + n.height / 2}`)
            .datum(n)
            .on("click", function () {
                highlightPath(n.id, graphData, tangleLayout.nodes, edges); // Call the highlight function with the selected node ID
            });

        graphGroup
            .append("path")
            .attr("class", "node")
            .attr("stroke", "white")
            .attr("stroke-width", 4)
            .attr("d", `M${n.x} ${n.y - n.height / 2} L${n.x} ${n.y + n.height / 2}`)
            .datum(n)
            .on("click", function () {
                highlightPath(n.id, graphData, tangleLayout.nodes, edges); // Call the highlight function with the selected node ID
            });

        graphGroup
            .append("text")
            .attr("class", "selectable")
            .attr("data-id", n.id)
            .attr("x", n.x + 4)
            .attr("y", n.y - n.height / 2 - 4)
            .attr("stroke", background_color)
            .attr("stroke-width", 2)
            .text(n.id);

        graphGroup
            .append("text")
            .attr("x", n.x + 4)
            .attr("y", n.y - n.height / 2 - 4)
            .style("pointer-events", "none")
            .text(n.id);
    });

    // After rendering the graph, calculate the bounding box
    const bbox = graphGroup.node().getBBox(); // Get the bounding box of the graph group

    // Calculate the scale to fit the graph within the 1200x800 canvas
    const canvasWidth = 1200;
    const canvasHeight = 800;
    const scaleX = canvasWidth / (bbox.width + 30);
    const scaleY = canvasHeight / (bbox.height + 30);
    const initialScale = Math.min(scaleX, scaleY); // Use the smaller scale to fit both dimensions

    // Center the graph in the canvas
    const translateXpost =
        (canvasWidth - (bbox.width + 30) * initialScale) / 2 - bbox.x * initialScale;
    const translateYpost =
        (canvasHeight - (bbox.height + 30) * initialScale) / 2 - bbox.y * initialScale;

    // Set the initial transform
    graphGroup.attr(
        "transform",
        `translate(${translateXpost}, ${translateYpost}) scale(${initialScale})`,
    );

    // Store the initial transform for resetting zoom
    initialTransform = d3.zoomIdentity
        .translate(translateXpost, translateYpost)
        .scale(initialScale);
}

function createStar(cx, cy, outerRadius, innerRadius) {
    const points = [];
    const numPoints = 5;

    for (let i = 0; i < numPoints * 2; i++) {
        const angle = (i * Math.PI) / numPoints; // Angle for each point
        const radius = i % 2 === 0 ? outerRadius : innerRadius; // Alternate between outer and inner radius
        const x = cx + Math.cos(angle) * radius; // Calculate x coordinate
        const y = cy + Math.sin(angle) * radius; // Calculate y coordinate
        points.push(`${x},${y}`); // Add point to the array
    }

    return `M${points.join(" L")} Z`; // Create the path string
}

function highlightPath(selectedNodeId, graphData, nodes, edges) {
    const selectedNode = nodes.find((node) => node.id === selectedNodeId);

    // Reset previous highlights
    d3.selectAll(".selectable.node")
        .classed("highlight", false) // Remove highlight class
        .attr("stroke-width", 8)
        .attr("stroke", "black")
        .attr("fill", "black")
        .attr("d", function () {
            const n = d3.select(this).datum(); // Get the bound data
            return `M${n.x} ${n.y - n.height / 2} L${n.x} ${n.y + n.height / 2}`; // Reset shape to original
        });

    if (!selectedNode) return; // Exit if the node is not found

    // // Define the dimensions for the star shape
    const outerRadius = 8; // Outer radius of the star
    const innerRadius = 4; // Inner radius of the star

    // Highlight the selected node
    d3.select(`[data-id="${selectedNodeId}"]`)
        .classed("highlight", true) // Add highlight class
        .attr("stroke-width", 4) // Increase stroke width
        .attr("stroke", "#0093b1")
        .attr("fill", "white")
        .attr(
            "d",
            createStar(selectedNode.x, selectedNode.y, outerRadius, innerRadius),
        );

    // Find all relevant entries in graphData for the selected node
    const relevantEntries = graphData.filter((entry) => entry.name === selectedNodeId);

    // Create a set to store unique node names based on time and name
    const nodeNamesToHighlight = new Set();

    relevantEntries.forEach((entry) => {
        // Create the node name in the format "${time} ${name}"
        const nodeName = `${entry.time} ${entry.executable}`;
        nodeNamesToHighlight.add(nodeName);
    });

    // Collect all relevant source IDs from relevantEntries
    const relevantSourceIds = relevantEntries.map((entry) => entry.name);
    nodeNamesToHighlight.forEach((relevantId) => {
        d3.select(`[data-id="${relevantId}"]`)
            .classed("highlight", true) // Add highlight class
            .attr("stroke-width", 4) // Increase stroke width
            .attr("stroke", "#0093b1")
            .attr("fill", "white")
            .attr("d", function () {
                const n = d3.select(this).datum(); // Get the bound data
                return createStar(n.x, n.y, outerRadius, innerRadius);
            });
    });
}

function downloadSVG() {
    const svg = document.getElementById("graph");

    // Calculate the bounding box of the SVG content
    const bbox = svg.getBBox();

    // Define padding
    const padding = 20; // Adjust this value as needed

    // Create a clone of the original SVG
    const clonedSVG = svg.cloneNode(true);

    // Set the viewBox to match the bounding box with padding
    clonedSVG.setAttribute(
        "viewBox",
        `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + 2 * padding} ${bbox.height + 2 * padding}`,
    );

    // Optionally, set the width and height to match the bounding box
    clonedSVG.setAttribute("width", bbox.width + 2 * padding);
    clonedSVG.setAttribute("height", bbox.height + 2 * padding);

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(clonedSVG);

    // Create a Blob from the SVG string
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    // Create a link element to trigger the download
    const link = document.createElement("a");
    link.href = url;
    link.download = "vm_resource_graph.svg"; // Set the file name

    // Append to the body, click and remove
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Release the object URL
    URL.revokeObjectURL(url);
}

function resetZoom() {
    // Reset previous highlights
    d3.selectAll(".selectable.node")
        .classed("highlight", false) // Remove highlight class
        .attr("stroke-width", 8)
        .attr("stroke", "black")
        .attr("d", function () {
            const n = d3.select(this).datum(); // Get the bound data
            return `M${n.x} ${n.y - n.height / 2} L${n.x} ${n.y + n.height / 2}`; // Reset shape to original
        });

    const svg = d3.select("#graph");
    const graphGroup = d3.select("#graph").select("g");
    graphGroup.transition().duration(750).attr("transform", initialTransform);
    const zoom = d3
        .zoom()
        .scaleExtent([0.05, 5]) // Set the zoom scale limits
        .on("zoom", (event) => {
            graphGroup.attr("transform", event.transform); // Apply the zoom transformation
        });
    svg.transition().duration(750).call(zoom.transform, initialTransform);
}

// Attach the reset function to the reset icon
const resetIcon = document.getElementById("resetIcon");
resetIcon.addEventListener("click", resetZoom);
const resettooltip = document.getElementById("resettooltip");

// Show tooltip on mouse enter
resetIcon.addEventListener("mouseenter", () => {
    resettooltip.style.display = "block"; // Show the tooltip
});

// Hide tooltip on mouse leave
resetIcon.addEventListener("mouseleave", () => {
    resettooltip.style.display = "none"; // Hide the tooltip
});

// Attach the download function to the SVG icon
const downloadIcon = document.getElementById("downloadIcon");
const downloadtooltip = document.getElementById("downloadtooltip");

downloadIcon.addEventListener("click", downloadSVG);

// Show tooltip on mouse enter
downloadIcon.addEventListener("mouseenter", () => {
    downloadtooltip.style.display = "block"; // Show the tooltip
});

// Hide tooltip on mouse leave
downloadIcon.addEventListener("mouseleave", () => {
    downloadtooltip.style.display = "none"; // Hide the tooltip
});

function convertToTangledTreeData(serverNodes, timeNodes, edges) {
    // Initialize the data structure
    const data = [];

    // Level 0: Server Nodes
    const serverLevel = serverNodes.map((server) => ({
        id: server.name,
        parents: Array(),
    }));
    data.push(serverLevel);

    // Level 1: Time Nodes
    // Create a sorted array of unique times
    const sortedUniqueTimes = Array.from(new Set(timeNodes.map((node) => node.time)))
        .map(Number) // Convert to numbers
        .sort((a, b) => a - b); // Sort from most negative to most positive

    sortedUniqueTimes.forEach((uniqueTime) => {
        const parents = Array.from(
            new Set(
                edges
                    .filter((edge) => edge.target.time === uniqueTime)
                    .map((edge) =>
                        edge.source.time
                            ? `${edge.source.time} ${edge.source.name}`
                            : edge.source.name,
                    ), // Get parent server names
            ),
        );

        const matchingTimeNodes = timeNodes.filter((node) => node.time === uniqueTime);

        // Create an array for the current time level
        const currentTimeLevel = matchingTimeNodes.map((timeNode) => ({
            id: `${uniqueTime} ${timeNode.name}`,
            parents: parents,
        }));

        // Push the current time level array to data
        data.push(currentTimeLevel);
    });

    return combineNodesWithSameId(data);
}

function combineNodesWithSameId(levels) {
    const combinedLevels = [];

    levels.forEach((level) => {
        const combinedMap = new Map();

        level.forEach((node) => {
            // Check if the node has an id
            if (!node.id) {
                console.warn("Node is missing an id:", node);
                return; // Skip this node if it doesn't have an id
            }

            // Ensure parents is defined and is an array
            if (!Array.isArray(node.parents)) {
                console.warn(
                    "Node is missing parents or parents is not an array:",
                    node,
                );
                node.parents = []; // Initialize parents as an empty array if undefined
            }

            // If the node already exists, merge parents
            if (combinedMap.has(node.id)) {
                const existingNode = combinedMap.get(node.id);
                existingNode.parents = Array.from(
                    new Set([...existingNode.parents, ...node.parents]),
                ); // Merge parents and remove duplicates
            } else {
                // If the node does not exist, add it to the map
                combinedMap.set(node.id, { id: node.id, parents: [...node.parents] });
            }
        });

        // Convert the map back to an array and push to combinedLevels
        combinedLevels.push(Array.from(combinedMap.values()));
    });

    return combinedLevels;
}

function constructTangleLayout(levels, options = {}) {
    // precompute level depth
    levels.forEach((l, i) => l.forEach((n) => (n.level = i)));

    var nodes = levels.reduce((a, x) => a.concat(x), []);
    var nodes_index = {};
    nodes.forEach((d) => (nodes_index[d.id] = d));

    // objectification
    nodes.forEach((d) => {
        d.parents = (d.parents === undefined ? [] : d.parents).map(
            (p) => nodes_index[p],
        );
    });

    // precompute bundles
    levels.forEach((l, i) => {
        var index = {};
        l.forEach((n) => {
            if (n.parents.length == 0) {
                return;
            }

            var id = n.parents
                .map((d) => d.id)
                .sort()
                .join("-X-");
            if (id in index) {
                index[id].parents = index[id].parents.concat(n.parents);
            } else {
                index[id] = {
                    id: id,
                    parents: n.parents.slice(),
                    level: i,
                    span: i - d3.min(n.parents, (p) => p.level),
                };
            }
            n.bundle = index[id];
        });
        l.bundles = Object.keys(index).map((k) => index[k]);
        l.bundles.forEach((b, i) => (b.i = i));
    });

    var links = [];
    nodes.forEach((d) => {
        d.parents.forEach((p) =>
            links.push({ source: d, bundle: d.bundle, target: p }),
        );
    });

    var bundles = levels.reduce((a, x) => a.concat(x.bundles), []);

    // reverse pointer from parent to bundles
    bundles.forEach((b) =>
        b.parents.forEach((p) => {
            if (p.bundles_index === undefined) {
                p.bundles_index = {};
            }
            if (!(b.id in p.bundles_index)) {
                p.bundles_index[b.id] = [];
            }
            p.bundles_index[b.id].push(b);
        }),
    );

    nodes.forEach((n) => {
        if (n.bundles_index !== undefined) {
            n.bundles = Object.keys(n.bundles_index).map((k) => n.bundles_index[k]);
        } else {
            n.bundles_index = {};
            n.bundles = [];
        }
        n.bundles.sort((a, b) =>
            d3.descending(
                d3.max(a, (d) => d.span),
                d3.max(b, (d) => d.span),
            ),
        );
        n.bundles.forEach((b, i) => (b.i = i));
    });

    links.forEach((l) => {
        if (l.bundle.links === undefined) {
            l.bundle.links = [];
        }
        l.bundle.links.push(l);
    });

    // layout
    const padding = 8;
    const node_height = 22;
    const node_width = 70;
    const bundle_width = 14;
    const level_y_padding = 6;
    const metro_d = 4;
    const min_family_height = 10;

    options.c ||= 16;
    const c = options.c;
    options.bigc ||= node_width + c;

    nodes.forEach((n) => {
        n.height = (Math.max(1, n.bundles.length) - 1) * metro_d;
    });

    var x_offset = padding;
    var y_offset = padding;
    levels.forEach((l) => {
        x_offset += l.bundles.length * bundle_width;
        y_offset += level_y_padding;
        l.forEach((n, i) => {
            n.x = n.level * node_width + x_offset;
            n.y = node_height + y_offset + n.height / 2;

            y_offset += node_height + n.height;
        });
    });

    var i = 0;
    levels.forEach((l) => {
        l.bundles.forEach((b) => {
            b.x =
                d3.max(b.parents, (d) => d.x) +
                node_width +
                (l.bundles.length - 1 - b.i) * bundle_width;
            b.y = i * node_height;
        });
        i += l.length;
    });

    links.forEach((l) => {
        l.xt = l.target.x;
        l.yt =
            l.target.y +
            l.target.bundles_index[l.bundle.id].i * metro_d -
            (l.target.bundles.length * metro_d) / 2 +
            metro_d / 2;
        l.xb = l.bundle.x;
        l.yb = l.bundle.y;
        l.xs = l.source.x;
        l.ys = l.source.y;
    });

    // compress vertical space
    var y_negative_offset = 0;
    levels.forEach((l) => {
        y_negative_offset +=
            -min_family_height +
                d3.min(l.bundles, (b) =>
                    d3.min(b.links, (link) => link.ys - 2 * c - (link.yt + c)),
                ) || 0;
        l.forEach((n) => {
            // Modify n.y
            n.y -= y_negative_offset;
        });
    });

    // Update the bundle y-coordinates based on the new source node y-coordinates
    // Update the bundle y-coordinates based on the new source node y-coordinates
    levels.forEach((l) => {
        l.bundles.forEach((b) => {
            // Get the maximum y-coordinate of the source nodes from the links
            const sourceY = d3.max(b.links, (link) => link.source.y); // Use the updated source node y-coordinate

            // Set the bundle's y-coordinate to be at most the maximum y-coordinate of the source nodes
            b.y = Math.min(sourceY, b.y); // Ensure the bundle is not lower than the source node
        });
    });

    links.forEach((l) => {
        l.xt = l.target.x;
        l.yt =
            l.target.y +
            l.target.bundles_index[l.bundle.id].i * metro_d -
            (l.target.bundles.length * metro_d) / 2 +
            metro_d / 2;
        l.xb = l.bundle.x;
        l.yb = l.bundle.y;
        l.xs = l.source.x;
        l.ys = l.source.y;
    });

    // very ugly, I know
    links.forEach((l) => {
        l.yt =
            l.target.y +
            l.target.bundles_index[l.bundle.id].i * metro_d -
            (l.target.bundles.length * metro_d) / 2 +
            metro_d / 2;
        l.ys = l.source.y;

        // Calculate control points for arcs
        l.c1 =
            l.source.level - l.target.level > 1
                ? Math.min(options.bigc, Math.abs(l.xb - l.xt), Math.abs(l.yb - l.yt)) -
                  c
                : c;
        l.c2 = c;

        // Determine the sweep flag based on the positions
        // First arc
        l.sweepFlag1 = l.yt < l.ys ? 1 : 0;
        l.arc1Point = l.yt < l.ys ? l.yt + l.c1 : l.yt - l.c1;
        // Second Arc from bundle to target
        l.sweepFlag2 = l.ys < l.yt ? 1 : 0;
        l.arc2Point = l.ys < l.yt ? l.ys + l.c2 : l.ys - l.c2;
    });

    var layout = {
        width: d3.max(nodes, (n) => n.x) + node_width + 2 * padding,
        height: d3.max(nodes, (n) => n.y) + node_height / 2 + 2 * padding,
        node_height,
        node_width,
        bundle_width,
        level_y_padding,
        metro_d,
    };

    return { levels, nodes, nodes_index, links, bundles, layout };
}

// Function to filter the schedule
function filterSchedule(data, vmName, startTime, endTime) {
    const filteredData = {};

    // Return early if data is undefined or null
    if (data === undefined || data === null) {
        return filteredData;
    }

    Object.keys(data).forEach((time) => {
        const timeNum = parseInt(time);

        const isWithinStartTime = startTime === null || timeNum >= startTime;
        const isWithinEndTime = endTime === null || timeNum <= endTime;

        if (isWithinStartTime && isWithinEndTime) {
            const entries = data[time].filter((entry) => {
                return vmName
                    ? entry.name.toLowerCase().includes(vmName.toLowerCase())
                    : true;
            });

            if (entries.length > 0) {
                filteredData[time] = entries;
            }
        }
    });

    return filteredData;
}

// Get the modal
const graphInfoModal = document.getElementById("graphInfoModal");

// Get the button that opens the modal
const infoButton = document.getElementById("graphInfoButton");

// Get the <span> element that closes the modal
const closeButton = document.getElementById("graphInfoCloseButton");

// When the user clicks the button, open the modal
infoButton.onclick = function () {
    graphInfoModal.style.display = "block";
};

const detailsModal = document.getElementById("detailsModal");
const detailsModalCloseButton = document.getElementById("detailsModalCloseButton");

detailsModalCloseButton.onclick = function () {
    detailsModal.style.display = "none";
};

closeButton.onclick = function () {
    graphInfoModal.style.display = "none";
};

// When the user clicks anywhere outside of the modal, close it
window.onclick = function (event) {
    if (event.target === graphInfoModal) {
        graphInfoModal.style.display = "none";
    }
    if (event.target === detailsModal) {
        detailsModal.style.display = "none";
    }
};
