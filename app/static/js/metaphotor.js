$(function() {

	$("onLoad", function() {


	});  // onLoad function()

});  // function()


function get_city_coords(city) {
	$.getJSON("/_get_city_coords", {"city": city}, function(data) {
		if (data.error == "") {
		    $("#geo_latitude").val(data.latitude)
		    $("#geo_longitude").val(data.longitude)
		    $("#geo_country").val(data.country)
		    $("#geo_city").val(data.city)
		} else {
		    alert(data.error)
		    $("#geo_latitude").val("")
		    $("#geo_longitude").val("")
		    $("#geo_country").val("")
		}
	});  // getJSON
} // get_city_coords()


function scan_media() {
	scan_status_interval = setInterval(function() {
		scan_status()
	}, 1000); // time in milliseconds;

	$.getJSON("/_scan", function(data) {
		clearInterval(scan_status_interval);
		if ($("#scan_progress").html() == "") {
		    scan_status()
		}
	});  // getJSON
} // scan_media()


function scan_status() {
	$.getJSON("/_scan_status", function(data) {
		total = parseInt(data.total)
		passed = parseInt(data.passed)
		failed = parseInt(data.failed)
		progress = 100 * (passed + failed) / total
		content = "Total items found: " + total + '<div class="progress">'
		content += '<div class="progress-bar bg-info" role="progressbar" style="width: ' + progress + '%" aria-valuenow="' 
		content += (passed + failed) + '" aria-valuemin="0" aria-valuemax="' + total + '">' + progress + '%</div></div>'
		$("#scan_progress").html(content);
	});  // getJSON
} // scan_status()
