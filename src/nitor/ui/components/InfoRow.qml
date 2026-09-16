// A label/value row, used on the device and about pages.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: row

    required property string label
    required property string value
    property bool selectable: false

    Layout.fillWidth: true
    spacing: 12

    Label {
        Layout.preferredWidth: 140
        text: row.label
        opacity: 0.65
        elide: Text.ElideRight
    }

    Label {
        Layout.fillWidth: true
        text: row.value.length > 0 ? row.value : "—"
        wrapMode: Text.WrapAnywhere
        textFormat: Text.PlainText
        font.family: row.selectable ? "monospace" : ""
    }
}
