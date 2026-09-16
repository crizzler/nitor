// The screen that answers the five questions a user actually has: is my hardware here, which device
// am I controlling, what colour, which effect, which channel.

// Delegates read the page's own ids, which requires explicit bound component behaviour.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Page {
    id: page

    required property var app

    function effectTooltip(effect) {
        const parts = [effect.group];
        if (!effect.usesColors) {
            parts.push("no colour");
        } else if (effect.minColors === effect.maxColors) {
            parts.push(effect.maxColors + (effect.maxColors === 1 ? " colour" : " colours"));
        } else {
            parts.push(effect.minColors + "–" + effect.maxColors + " colours");
        }
        if (effect.supportsSpeed) {
            parts.push("speed");
        }
        if (effect.supportsDirection) {
            parts.push("direction");
        }
        return parts.join(" · ");
    }

    ScrollView {
        id: scroller
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 16

            RecoveryCard {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.topMargin: 20
                backendMissing: !page.app.backendAvailable
                backendSummary: page.app.backendSummary
                backendHint: page.app.backendHint
                installCommand: page.app.installCommand
                permissionDenied: page.app.accessDenied
                permissionHint: page.app.permissionHint
                onRecheckRequested: page.app.refresh()
                onCopyRequested: text => page.app.copyToClipboard(text)
            }

            // Nothing to control (yet): say so plainly instead of showing dead controls.
            Pane {
                Layout.fillWidth: true
                Layout.margins: 20
                visible: page.app.backendAvailable && !page.app.ready && !page.app.busy
                padding: 24

                background: Rectangle {
                    radius: 8
                    color: page.palette.alternateBase
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    Label {
                        Layout.fillWidth: true
                        text: "No compatible NZXT controller found"
                        font.bold: true
                        visible: !page.app.hasDevices
                    }

                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: page.app.hasDevices
                              ? "A device was detected, but Nitor cannot control its LEDs. " +
                                "See the Devices page for details."
                              : "Connect an NZXT RGB & Fan Controller or a Kraken Z series cooler, " +
                                "then choose Check again."
                    }

                    Button {
                        text: "Check again"
                        onClicked: page.app.refresh()
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                spacing: 16
                visible: page.app.ready

                SectionCard {
                    Layout.fillWidth: true
                    title: "Colour"
                    subtitle: page.app.effectsUseColors
                              ? "The LEDs will show this colour" + (page.app.brightness < 100 ? " at " + page.app.brightness + "% brightness" : "")
                              : "The selected effect generates its own colours"

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 20

                        ColorWheel {
                            id: wheel
                            Layout.preferredWidth: 176
                            Layout.preferredHeight: 176
                            enabled: page.app.effectsUseColors
                            hue: page.app.colorHue
                            saturation: page.app.colorSaturation
                            value: page.app.colorValue
                            borderColor: Qt.rgba(page.palette.text.r, page.palette.text.g, page.palette.text.b, 0.15)
                            onColorPicked: (red, green, blue) => page.app.setColorComponents(red, green, blue)
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            ColorSlotRow {
                                Layout.fillWidth: true
                                items: page.app.colorSlots
                                textColor: page.palette.text
                                onSlotChosen: index => page.app.selectColorSlot(index)
                            }

                            HexField {
                                Layout.fillWidth: true
                                colorHex: page.app.colorHex
                                enabled: page.app.effectsUseColors
                                onCommitted: text => page.app.setColorHex(text)
                            }

                            PresetSwatches {
                                Layout.fillWidth: true
                                items: page.app.presets
                                current: page.app.colorHex
                                textColor: page.palette.text
                                highlightColor: page.palette.highlight
                                enabled: page.app.effectsUseColors
                                onPicked: name => page.app.setPreset(name)
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 56
                                radius: 6
                                color: page.app.previewColor
                                border.width: 1
                                border.color: Qt.rgba(page.palette.text.r, page.palette.text.g, page.palette.text.b, 0.2)

                                Label {
                                    anchors.centerIn: parent
                                    visible: page.app.brightness < 100 && page.app.effectsUseColors
                                    text: "sending " + page.app.effectiveColor
                                    color: page.app.brightness < 45 ? "#ffffff" : "#101010"
                                    font.family: "monospace"
                                }
                            }
                        }
                    }
                }

                SectionCard {
                    Layout.fillWidth: true
                    title: "Effect"
                    subtitle: "Only effects this controller supports are listed"

                    ComboBox {
                        id: effectBox
                        Layout.fillWidth: true
                        model: page.app.effects
                        textRole: "label"
                        valueRole: "id"
                        currentIndex: {
                            for (let index = 0; index < page.app.effects.length; ++index) {
                                if (page.app.effects[index].id === page.app.effectId) {
                                    return index;
                                }
                            }
                            return -1;
                        }
                        onActivated: page.app.selectEffect(currentValue)

                        delegate: ItemDelegate {
                            id: effectRow
                            required property var modelData
                            required property int index

                            width: effectBox.width
                            text: modelData.label
                            highlighted: effectBox.highlightedIndex === index
                            ToolTip.visible: hovered
                            ToolTip.text: page.effectTooltip(modelData)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        visible: page.app.speedAvailable || page.app.directionAvailable

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            visible: page.app.speedAvailable

                            Label {
                                text: "Speed"
                                opacity: 0.65
                            }

                            ComboBox {
                                id: speedBox
                                Layout.fillWidth: true
                                model: page.app.speeds
                                currentIndex: Math.max(0, page.app.speeds.indexOf(page.app.speed))
                                onActivated: page.app.setSpeed(currentText)
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            visible: page.app.directionAvailable

                            Label {
                                text: "Direction"
                                opacity: 0.65
                            }

                            ComboBox {
                                id: directionBox
                                Layout.fillWidth: true
                                model: page.app.directions
                                currentIndex: Math.max(0, page.app.directions.indexOf(page.app.direction))
                                onActivated: page.app.setDirection(currentText)
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: !page.app.effectsUseColors
                        wrapMode: Text.WordWrap
                        opacity: 0.65
                        text: "This effect produces its own colours, so the colour picker and the " +
                              "brightness control do not apply to it."
                    }
                }

                SectionCard {
                    Layout.fillWidth: true
                    title: "Channel"
                    subtitle: "Each channel drives its own group of LEDs"

                    ComboBox {
                        id: channelBox
                        Layout.fillWidth: true
                        model: page.app.channels
                        textRole: "label"
                        valueRole: "id"
                        currentIndex: {
                            for (let index = 0; index < page.app.channels.length; ++index) {
                                if (page.app.channels[index].id === page.app.channelId) {
                                    return index;
                                }
                            }
                            return -1;
                        }
                        onActivated: page.app.selectChannel(currentValue)

                        delegate: ItemDelegate {
                            id: channelRow
                            required property var modelData
                            required property int index

                            width: channelBox.width
                            text: modelData.label
                            highlighted: channelBox.highlightedIndex === index
                            ToolTip.visible: hovered
                            ToolTip.text: modelData.summary
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: {
                            for (let index = 0; index < page.app.channels.length; ++index) {
                                if (page.app.channels[index].id === page.app.channelId) {
                                    return page.app.channels[index].summary === "No accessories detected";
                                }
                            }
                            return false;
                        }
                        wrapMode: Text.WordWrap
                        color: "#f8961e"
                        text: "Nothing is detected on this channel. Check that the LED strip or fan " +
                              "is connected and that the controller was initialised after a power loss."
                    }
                }

                SectionCard {
                    Layout.fillWidth: true
                    title: "Brightness"
                    subtitle: page.app.brightnessAvailable
                              ? "Dims the colour Nitor sends; these controllers have no brightness setting of their own"
                              : "Not applicable to the selected effect"

                    BrightnessSlider {
                        Layout.fillWidth: true
                        brightness: page.app.brightness
                        effectiveColor: page.app.effectiveColor
                        enabled: page.app.brightnessAvailable
                        onMoved: percent => page.app.setBrightness(percent)
                    }

                    RowLayout {
                        spacing: 8

                        Button {
                            text: "Apply now"
                            onClicked: page.app.applyNow()
                        }

                        Button {
                            text: "Turn off"
                            onClicked: page.app.turnOff()
                        }

                        Button {
                            text: "Reset"
                            onClicked: page.app.resetToDefaults()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: page.app.notices.length > 0

                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        opacity: 0.7
                        text: page.app.notices.join("\n")
                    }
                }
            }
        }
    }
}
