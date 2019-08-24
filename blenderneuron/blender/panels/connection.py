import bpy

from blenderneuron.blender.panels import AbstractBlenderNEURONPanel
from blenderneuron.blender.utils import blender_launched_neuron_running


class blenderneuron_nodes_panel(AbstractBlenderNEURONPanel, bpy.types.Panel):
    bl_label = "Node Status"

    def draw(self, context):

        self.set_node()

        if self.node is None or self.node.server is None:
            self.layout.label(text="Blender Node is not running")
            self.layout.prop(context.scene.BlenderNEURON_properties, "server_ip")
            self.layout.prop(context.scene.BlenderNEURON_properties, "server_port")
            self.layout.operator("blenderneuron.node_start", text="Start Blender Node", icon="PLAY")

        else:  # Node is running

            self.layout.label(text="NEURON Client Status")

            col = self.layout.box().column(align=True)

            if self.node.client is None:
                col.label(text="Status: Not Connected", icon="ERROR")
                col.prop(context.scene.BlenderNEURON_properties, "client_ip")
                col.prop(context.scene.BlenderNEURON_properties, "client_port")
                col.separator()
                col.operator("blenderneuron.try_connect_to_neuron", text="Try Connecting to NEURON", icon="PLAY")
                col.separator()

                if not blender_launched_neuron_running():
                    col.prop(context.scene.BlenderNEURON_properties, "neuron_launch_command")
                    col.operator("blenderneuron.launch_neuron", text="Launch NEURON", icon="PLAY")

            else:
                col.label(text="Status: Connected")
                col.label(text="Address: " + self.node.client_address)

            if blender_launched_neuron_running():
                col.separator()
                col.operator("blenderneuron.stop_neuron", text="Stop NEURON", icon="CANCEL")


            # ----------- #

            self.layout.label(text="Blender Server Status")

            col = self.layout.box().column(align=True)

            if self.node.server is None:
                col.label(text="Node Server Status: Stopped")
            else:
                col.label(text="Status: Listening")
                col.label(text="Address: " + self.node.server_address)

            # ----------- #

            self.layout.operator("blenderneuron.node_stop", text="Stop Blender Node", icon="CANCEL")

            self.layout.operator("blenderneuron.add_neon_effect", text="Add Neon Effect", icon="PARTICLES")
