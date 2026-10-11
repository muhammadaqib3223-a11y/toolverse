/* Profile photo, in the browser: crop it square and shrink it (max 512 px, JPEG) before it is
 * sent anywhere, so uploads stay small and fast. Drawing through a canvas also drops the
 * photo's hidden data (EXIF: GPS location, camera). The server checks and cleans it again. */
(function (window) {
  "use strict";

  var MAX_SIDE = 512;
  var MIN_SIDE = 64;
  var MAX_DATA_URL_LENGTH = 380000;  // ~280 KB of JPEG; the server allows 300 KB
  var QUALITIES = [0.86, 0.78, 0.68, 0.58];
  var TYPES = /^image\/(jpeg|png|webp)$/;

  function fail(code) {
    var error = new Error(code);
    error.code = code;
    return error;
  }

  // Resolves to a "data:image/jpeg;base64,..." string, or rejects with code
  // "photo_invalid" / "photo_too_large".
  function compress(file) {
    return new Promise(function (resolve, reject) {
      if (!file || !TYPES.test(file.type)) { reject(fail("photo_invalid")); return; }
      if (file.size > 25 * 1024 * 1024) { reject(fail("photo_too_large")); return; }
      var url = URL.createObjectURL(file);
      var image = new Image();
      image.onload = function () {
        URL.revokeObjectURL(url);
        var side = Math.min(image.naturalWidth, image.naturalHeight);
        if (side < MIN_SIDE) { reject(fail("photo_invalid")); return; }
        var size = Math.min(MAX_SIDE, side);
        var canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        var context = canvas.getContext("2d");
        context.fillStyle = "#ffffff";  // transparent PNGs get a white background, like paper
        context.fillRect(0, 0, size, size);
        context.drawImage(
          image,
          (image.naturalWidth - side) / 2, (image.naturalHeight - side) / 2, side, side,
          0, 0, size, size
        );
        for (var i = 0; i < QUALITIES.length; i++) {
          var dataUrl = canvas.toDataURL("image/jpeg", QUALITIES[i]);
          if (dataUrl.length <= MAX_DATA_URL_LENGTH) { resolve(dataUrl); return; }
        }
        reject(fail("photo_too_large"));
      };
      image.onerror = function () {
        URL.revokeObjectURL(url);
        reject(fail("photo_invalid"));
      };
      image.src = url;
    });
  }

  function blobToDataUrl(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { reject(fail("photo_invalid")); };
      reader.readAsDataURL(blob);
    });
  }

  window.CvPhoto = { compress: compress, blobToDataUrl: blobToDataUrl };
})(window);
