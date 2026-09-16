// The window shell: a sidebar for navigation, a header for the device, and a footer that always
// says what just happened.

// Delegates read the component's own ids, which requires explicit bound component behaviour.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "pages"
import "components"

ApplicationWindow {
    id: root

    // Supplied by the Python side as an initial property. Declaring it here (rather than relying on
    // a context property) is what lets qmllint and the QML compiler see the view model at all.
    required property var app

    property int currentPage: 0
    readonly property var navigation: ["Lighting", "Devices", "Settings", "About"]

    minimumWidth: 820
    minimumHeight: 560
    title: root.app.appName
    visible: true

    Component.onCompleted: {
        // Assigned rather than bound, so the window manager stays in charge of resizing.
        width = root.app.windowWidth;
        height = root.app.windowHeight;
        root.app.start();
        root.app.queryAutostart();
    }

    onClosing: root.app.saveWindowState(width, height)

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                Layout.leftMargin: 4
                text: root.app.appName
                font.bold: true
                font.pointSize: Math.round(root.app.baseFontPointSize * 1.2)
            }

            Item {
                Layout.fillWidth: true
            }

            Label {
                visible: root.app.mockMode
                text: "mock device"
                color: "#f8961e"
                padding: 4
                font.pointSize: Math.round(root.app.baseFontPointSize * 0.9)
                ToolTip.visible: mockBadgeHover.hovered
                ToolTip.text: "Development mode: no real hardware is being touched."

                HoverHandler {
                    id: mockBadgeHover
                }
            }

            ComboBox {
                id: deviceBox
                visible: root.app.devices.length > 0
                Layout.preferredWidth: Math.min(280, implicitWidth)
                model: root.app.devices
                textRole: "name"
                valueRole: "key"
                enabled: root.app.devices.length > 1
                currentIndex: {
                    for (let index = 0; index < root.app.devices.length; ++index) {
                        if (root.app.devices[index].current) {
                            return index;
                        }
                    }
                    return 0;
                }
                onActivated: root.app.selectDevice(currentValue)
            }

            Button {
                text: "Refresh"
                onClicked: root.app.refresh()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: root.palette.alternateBase

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 4

                Repeater {
                    model: root.navigation

                    delegate: ItemDelegate {
                        id: navigationItem
                        required property string modelData
                        required property int index

                        Layout.fillWidth: true
                        text: navigationItem.modelData
                        highlighted: root.currentPage === navigationItem.index
                        onClicked: root.currentPage = navigationItem.index
                    }
                }

                Item {
                    Layout.fillHeight: true
                }

                Label {
                    Layout.fillWidth: true
                    Layout.margins: 6
                    wrapMode: Text.WordWrap
                    opacity: 0.55
                    font.pointSize: Math.round(root.app.baseFontPointSize * 0.85)
                    text: root.app.currentDeviceName.length > 0 ? root.app.currentDeviceName : "No device"
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: root.currentPage

                LightingPage { app: root.app }
                DevicesPage { app: root.app }
                SettingsPage { app: root.app }
                AboutPage { app: root.app }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: footerContents.implicitHeight + 16
                color: root.palette.alternateBase

                ColumnLayout {
                    id: footerContents
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 12
                    spacing: 2

                    StatusPill {
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        kind: root.app.statusKind
                        message: root.app.statusMessage
                        textColor: root.palette.text
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        visible: root.app.statusHint.length > 0
                        text: root.app.statusHint
                        wrapMode: Text.WordWrap
                        opacity: 0.75
                        font.pointSize: Math.round(root.app.baseFontPointSize * 0.9)
                    }
                }
            }
        }
    }
}
