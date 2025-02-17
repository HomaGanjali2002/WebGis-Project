// Initial map settings
var map;
var wmsLayer;
var popup;

// Function to initialize the map with a padded extent
function initMap() {
  // Original geographic extent (Manhattan in EPSG:4326)
  var originalExtent = [-74.0479, 40.6829, -73.9067, 40.8798];
  var padding = -0.5;
  
  // Create a padded extent so that the shapefile does not touch the container edges
  var paddedExtent = [
    originalExtent[0] + padding, // minX
    originalExtent[1] + padding, // minY
    originalExtent[2] - padding, // maxX
    originalExtent[3] - padding  // maxY
  ];
  
  // Create OSM basemap layer with semi-transparency
  var osmLayer = new ol.layer.Tile({
    source: new ol.source.OSM(),
    opacity: 0.7 // Set opacity to 70% (30% transparency)
  });

  // Create WMS source from GeoServer
  wmsLayer = new ol.layer.Image({
    source: new ol.source.ImageWMS({
      url: 'http://localhost:8080/geoserver/WebGis_Project/wms',
      params: {
        'LAYERS': 'WebGis_Project:taxi_zones',
        'TILED': true,
        'CRS': 'EPSG:4326',
        'VERSION': '1.1.0'
      },
      serverType: 'geoserver',
      ratio: 1
    })
  });

  // Create view with CRS:4326
  var view = new ol.View({
    projection: 'EPSG:4326',
    center: ol.extent.getCenter(paddedExtent),
    zoom: 12,
    extent: paddedExtent
  });

  // Create map
  map = new ol.Map({
    target: 'map',
    layers: [osmLayer, wmsLayer], // Add OSM layer first, then WMS layer
    view: view
  });

  // Create Popup
  popup = new ol.Overlay({
    element: document.getElementById('popup'),
    positioning: 'bottom-center',
    stopEvent: false
  });
  map.addOverlay(popup);

  // Add event to display information
  map.on('click', function(evt) {
    var viewResolution = view.getResolution();
    var url = wmsLayer.getSource().getFeatureInfoUrl(
      evt.coordinate,
      viewResolution,
      'EPSG:4326',
      {'INFO_FORMAT': 'application/json'}
    );

    if (url) {
      fetch(url)
        .then(response => response.json())
        .then(data => {
          if (data.features.length > 0) {
            var props = data.features[0].properties;
            var content = `<div>
              <b>Zone Name:</b> ${props.zone}<br>
              <b>Demand:</b> ${props.taxi_demand}<br>
              <b>Landuse:</b> ${props.land_use}
            </div>`;
            popup.getElement().innerHTML = content;
            popup.setPosition(evt.coordinate);

            // Automatically close the popup after 5 seconds
            setTimeout(function() {
            popup.setPosition(undefined); // Hide the popup
            }, 5000);
          }
        });
    }
  });
}

// Load data from server
function loadTaxiDemandData() {
  const day = document.getElementById('day').value;
  const hour = document.getElementById('hour').value;

  fetch(`/api/update_taxi_demand?day=${day}&hour=${hour}`)
    .then(response => response.json())
    .then(data => {
      console.log('Update Success:', data.message);
      // Refresh WMS layer
      wmsLayer.getSource().updateParams({
        'TIME': new Date().getTime()
      });
      updateLanduseDemand();
    });
}

// Update Landuse panel
function updateLanduseDemand() {
  fetch('/api/landuse_demand')
    .then(response => response.json())
    .then(data => {
      let html = '<table class="table table-sm">';
      html += '<tr><th>Landuse</th><th>Demand</th></tr>';
      data.forEach(row => {
        html += `<tr><td>${row.landuse}</td><td>${row.total_demand}</td></tr>`;
      });
      html += '</table>';
      document.getElementById('landuse-content').innerHTML = html;
    });
}

// Initialize map after page load
window.onload = initMap;