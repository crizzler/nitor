// Device information: enough for a bug report, without drowning anyone in USB internals.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Page {
    id: page

    ScrollView {
        id: scroller
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 16

            SectionCard {
                Layout.fillWidth: true
                Layout.margins: 20
                title: app.currentDeviceName.length > 0 ? app.currentDeviceName : "No device selected"
                subtitle: app.currentDeviceName.length > 0
                          ? "The controller Nitor is talking to"
                          : "Connect a supported controller and choose Check again"

                InfoRow {
                    Layout.fillWidth: true
                    visible: app.currentDeviceUsbId.length > 0
                    label: "USB vendor"
                    value: app.currentDeviceUsbId.length > 0 ? app.currentDeviceUsbId.substring(0, 4) : ""
                    selectable: true
                }

                InfoRow {
                    Layout.fillWidth: true
                    visible: app.currentDeviceUsbId.length > 0
                    label: "USB product"
                    value: app.currentDeviceUsbId.length > 4 ? app.currentDeviceUsbId.substring(5) : ""
                    selectable: true
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Status"
                    value: !app.backendAvailable ? "Backend not installed"
                           : app.accessDenied ? "Connected, but access denied"
                           : app.ready ? "Connected" : "Not initialised"
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Backend"
                    value: app.backendSummary
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Driver"
                    value: app.currentDeviceDriver
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Firmware"
                    value: app.currentDeviceFirmware
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Device path"
                    value: app.currentDeviceAddress
                    selectable: true
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Channels"
                    value: app.channels.length.toString()
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Permissions"
                    value: app.accessDenied ? "Denied" : "OK"
                }

                RowLayout {
                    spacing: 8

                    Button {
                        text: "Check again"
                        onClicked: app.refresh()
                    }
                }
            }

            SectionCard {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                title: "Detected devices"
                subtitle: "Everything Nitor found on this system"

                Repeater {
                    model: app.devices

                    delegate: Pane {
                        id: deviceRow
                        required property var modelData
                        Layout.fillWidth: true
                        padding: 12

                        background: Rectangle {
                            radius: 6
                            color: deviceRow.modelData.current
                                   ? Qt.rgba(page.palette.highlight.r, page.palette.highlight.g, page.palette.highlight.b, 0.18)
                                   : Qt.rgba(page.palette.text.r, page.palette.text.g, page.palette.text.b, 0.05)
                        }

                        RowLayout {
                            anchors.fill: parent
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Label {
                                    text: deviceRow.modelData.name
                                    font.bold: true
                                }

                                Label {
                                    Layout.fillWidth: true
                                    text: deviceRow.modelData.usbId + " · " + deviceRow.modelData.driver
                                    opacity: 0.65
                                    font.family: "monospace"
                                }

                                Label {
                                    Layout.fillWidth: true
                                    visible: deviceRow.modelData.note.length > 0
                                    text: deviceRow.modelData.note
                                    wrapMode: Text.WordWrap
                                    color: "#f8961e"
                                }
                            }

                            Button {
                                text: deviceRow.modelData.current ? "Selected" : "Select"
                                enabled: deviceRow.modelData.lightingSupported && !deviceRow.modelData.current
                                onClicked: app.selectDevice(deviceRow.modelData.key)
                            }
                        }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: app.devices.length === 0
                    opacity: 0.7
                    wrapMode: Text.WordWrap
                    text: "No supported NZXT device was found. Check that it appears in lsusb and that " +
                          "nothing else is holding it open."
                }
            }
        }
    }
}
