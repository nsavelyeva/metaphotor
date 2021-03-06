$(function() {

	$("onLoad", function() {

		$("#carousel_album").bind("slide.bs.carousel", function (e) {
			// Increment visits and set current date & time as accessed value
			// on slide change in carousel (mediagallery.html template)
			mediafile_id = $(this).find(".active").data("mediafile_id")
			update_visits_accessed(Number(mediafile_id))
		});

        $('form:has("#folder")').on('keyup keypress', function(e) {
            // Disable submitting the form on Enter - applies for forms having elements with id='folder'.
            // In metaphotor, there is only one such form - the one used to upload a new media file: /mediafiles/add.
            var keyCode = e.keyCode || e.which;
            if (keyCode === 13) {
                e.preventDefault();
                return false;
            }
        });

        $('#folder').easyAutocomplete({
            // When uploading a new media file, give hints on file locations.
            url: function(folder) {
                return '/_hint?folder=' + folder
            },
            list: {
                match: { enabled: true },
                sort: { enabled: true }
            },
            getValue: 'hint'
        });

	});  // onLoad function()

});  // function()


function get_city_coords(city) {
	// Load geo coordinates, country and country code for the given city,
	// used in the form to add locations
	$.getJSON("/_get_city_coords", {"city": city}, function(data) {
		if (data.error == "") {
			$("#geo_latitude").val(data.latitude)
			$("#geo_longitude").val(data.longitude)
			$("#geo_country").val(data.country)
			$("#geo_city").val(data.city)
			$("#geo_code").val(data.code)
		} else {
			alert(data.error)
			$("#geo_latitude").val("")
			$("#geo_longitude").val("")
			$("#geo_country").val("")
			$("#geo_code").val("")
		}
	});  // getJSON
}  // get_city_coords()


function load_coords() {
	// In the form to edit a media file, on location change, fill in "Coordinates" field:
	// if "Location" field is changed to "unknown" place, clear "Coordinates" field;
	// otherwise, load coordinates of city center of "Location" field has been changed to.
	coords = document.getElementById("coords").value
	city = $("#location_id option:selected").html().split(", ")[0].toLowerCase()
	if (city == "unknown") {
        coords = ""
        $("#coords").val("")
    }
	else {
        $.getJSON("/_load_coords", {"city": city, "coords": coords}, function(data) {
            $("#coords").val(data.coords)
        });  // getJSON
    }
}  // load_coords()


function scan_media(increment=false) {
	// Start scan of media folder in parallel
	// and start timer to update progress bar (update interval is 1 second)
	scan_status_interval = setInterval(function() {
		scan_status()
	}, 1000); // time in milliseconds;

    ajax_path = increment ? "/_scan_increment" : "/_scan";

	$.getJSON(ajax_path, function(data) {
		if ($("#scan_progress").html() == "") {
		    scan_status()
		}
	});  // getJSON
}  // scan_media()


function scan_status() {
	// Read scan progress from server and update statistics and refresh progress bar;
	// if total is 0 or once 100% (passed + failed == total) is reached, stop calling for scan process updates.
	$.getJSON("/_scan_status", function(data) {
		total = parseInt(data.total)
		passed = parseInt(data.passed)
		failed = parseInt(data.failed)
		declined = data.declined == '' ? '<span style="color: green">None</span>' : data.declined
		progress = total == 0 ? 0 : Math.ceil(100 * (passed + failed) / (1.0 * total))
		content = '<span>Total items found: ' + total + '</span><div class="progress">'
		content += '<div class="progress-bar bg-info" role="progressbar" style="width: ' + progress + '%" aria-valuenow="' 
		content += (passed + failed) + '" aria-valuemin="0" aria-valuemax="' + total + '">' + progress + '%</div></div>'
		content += '<span style="color: green">Passed: ' + passed + '</span><br>'
		content += '<span style="color: red">Failed: ' + failed + '</span><br><br>'
		content += '<span>Declined files:</span><br><pre style="color: red">' + declined.replace(/;/g, '<br>') + '</pre>'
		$("#scan_progress").html(content);
		if (total >= 0 && passed + failed == total) {
			clearInterval(scan_status_interval)
		}
	});  // getJSON
}  // scan_status()


function show_mediafile_preview(mediafile_id, mediafile_path) {
	// Load photo or video file in the div container and update "visits" & "accessed" values
	content = $("#preview-" + mediafile_id).html()
	if (content == "") {
		if (mediafile_path.toLowerCase().endsWith(".jpg") || mediafile_path.toLowerCase().endsWith(".jpeg")) {
			content = '<img src="/load_mediafile' + mediafile_path + '" style="max-width: 100%" />'
		} else {
			content =	'<video controls="controls" preload="metadata" style="max-width: 100%">' +
						'<source src="/load_mediafile' + mediafile_path + '">' +
						'</video>'
		}
	} else {
		content = ""
	}
	$("#preview-" + mediafile_id).html(content);
	update_visits_accessed(mediafile_id)
}  // show_mediafile_preview()


function update_visits_accessed(mediafile_id) {
	// Increment visits and set current date & time as accessed value for the given mediafile
	$.getJSON("/_update_visits_accessed", {"mediafile_id": mediafile_id}, function(data) {
		if (data.error != "") {
			alert(data.error)
		}
	});  // getJSON
}  // update_visits_accessed()
