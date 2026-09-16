// Hue and saturation picker.
//
// The wheel edits hue (angle) and saturation (radius). Value comes from the colour already chosen,
// so the wheel never silently changes how bright the LEDs are; the Brightness control owns that,
// and it is honest software dimming because the hardware has no brightness register for these
// channels.

import QtQuick

Item {
    id: wheel

    //: Current colour, in HSV terms.
    property real hue: 0
    property real saturation: 0
    property real value: 100

    signal colorPicked(real red, real green, real blue)

    implicitWidth: 200
    implicitHeight: 200
    opacity: enabled ? 1.0 : 0.4

    function hsvToRgb(h, s, v) {
        const saturation = Math.max(0, Math.min(100, s)) / 100;
        const value = Math.max(0, Math.min(100, v)) / 100;
        const chroma = value * saturation;
        const sector = ((h % 360) + 360) % 360 / 60;
        const second = chroma * (1 - Math.abs((sector % 2) - 1));
        let red = 0, green = 0, blue = 0;
        if (sector < 1) { red = chroma; green = second; }
        else if (sector < 2) { red = second; green = chroma; }
        else if (sector < 3) { green = chroma; blue = second; }
        else if (sector < 4) { green = second; blue = chroma; }
        else if (sector < 5) { red = second; blue = chroma; }
        else { red = chroma; blue = second; }
        const match = value - chroma;
        return [Math.round((red + match) * 255), Math.round((green + match) * 255), Math.round((blue + match) * 255)];
    }

    function pickAt(x, y) {
        if (!enabled) {
            return;
        }
        const centreX = canvas.width / 2;
        const centreY = canvas.height / 2;
        const radius = Math.min(centreX, centreY);
        const dx = x - centreX;
        const dy = y - centreY;
        const distance = Math.min(Math.sqrt(dx * dx + dy * dy), radius);
        let angle = Math.atan2(dy, dx) * 180 / Math.PI;
        if (angle < 0) {
            angle += 360;
        }
        const pickedHue = angle;
        const pickedSaturation = radius > 0 ? (distance / radius) * 100 : 0;
        const rgb = hsvToRgb(pickedHue, pickedSaturation, wheel.value);
        wheel.colorPicked(rgb[0], rgb[1], rgb[2]);
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative

        onPaint: {
            const context = getContext("2d");
            context.reset();
            const centreX = width / 2;
            const centreY = height / 2;
            const radius = Math.min(centreX, centreY);

            // One thin wedge per degree, each a gradient from white to the wedge's hue. Drawn once
            // per resize, which keeps the wheel accurate rather than merely decorative.
            for (let angle = 0; angle < 360; angle += 1) {
                const start = (angle - 0.6) * Math.PI / 180;
                const end = (angle + 0.6) * Math.PI / 180;
                const edge = hsvToRgb(angle, 100, 100);
                const gradient = context.createLinearGradient(
                    centreX, centreY,
                    centreX + Math.cos(start) * radius, centreY + Math.sin(start) * radius);
                gradient.addColorStop(0, "rgb(255, 255, 255)");
                gradient.addColorStop(1, `rgb(${edge[0]}, ${edge[1]}, ${edge[2]})`);
                context.beginPath();
                context.moveTo(centreX, centreY);
                context.arc(centreX, centreY, radius, start, end);
                context.closePath();
                context.fillStyle = gradient;
                context.fill();
            }

            // Faint rim, so the wheel reads correctly on both light and dark desktops.
            context.beginPath();
            context.arc(centreX, centreY, radius - 1, 0, 2 * Math.PI);
            context.strokeStyle = wheel.borderColor;
            context.lineWidth = 2;
            context.stroke();
        }
    }

    property color borderColor: "transparent"

    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    onBorderColorChanged: canvas.requestPaint()

    // Marker for the current hue and saturation.
    Rectangle {
        x: canvas.width / 2 + Math.cos(hue * Math.PI / 180) * (Math.min(canvas.width, canvas.height) / 2) * (saturation / 100) - width / 2
        y: canvas.height / 2 + Math.sin(hue * Math.PI / 180) * (Math.min(canvas.width, canvas.height) / 2) * (saturation / 100) - height / 2
        width: 16
        height: 16
        radius: 8
        color: "transparent"
        border.width: 2
        border.color: "white"
        visible: wheel.enabled

        Rectangle {
            anchors.centerIn: parent
            width: 6
            height: 6
            radius: 3
            color: "transparent"
            border.width: 1
            border.color: "#202020"
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: wheel.enabled
        cursorShape: Qt.CrossCursor
        onPressed: mouse => wheel.pickAt(mouse.x, mouse.y)
        onPositionChanged: mouse => {
            if (mouse.buttons & Qt.LeftButton) {
                wheel.pickAt(mouse.x, mouse.y);
            }
        }
        // A drag is a sequence of picks; the scheduler coalesces them into one hardware write.
        onReleased: mouse => wheel.pickAt(mouse.x, mouse.y)
    }
}
