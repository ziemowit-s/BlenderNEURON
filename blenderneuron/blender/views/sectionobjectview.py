from blenderneuron.blender.views.objectview import ObjectViewAbstract
import bpy


class SectionObjectView(ObjectViewAbstract):
    def show(self):
        if self.group.recording_granularity != "Section":
            raise NotImplementedError()

        for root in self.group.roots.values():
            self.create_container_for_each_section(root)

        self.link_containers()

        self.parent_containers()

    def parent_containers(self):
        """
        Create parent-child relationship between section-child_section blender objects. This
        function can only be called if the parent and child containers have been linked to the
        scene.
        """

        for root in self.group.roots.values():
            self.set_childrens_parent(root)

    def set_childrens_parent(self, parent_sec, recursive=True):
        parent_cont = self.containers[parent_sec.hash]

        for child_sec in parent_sec.children:
            child_cont = self.containers[child_sec.hash]

            child_cont.set_parent_object(parent_cont)

            del child_cont

        del parent_cont

        if recursive:
            for child_sec in parent_sec.children:
                self.set_childrens_parent(child_sec)

    def create_container_for_each_section(self, root, recursive=True, is_top_level=True):
        if is_top_level:
            origin_type = "center"
        else:
            origin_type = "first"

        self.create_section_container(root, include_children=False, origin_type=origin_type)

        if recursive:
            for child in root.children:
                self.create_container_for_each_section(child, recursive=True, is_top_level=False)

    def update_group(self):
        for root in self.group.roots.values():
            self.update_each_container_section(root)

    def update_each_container_section(self, section):
        container = self.containers.get(section.hash)

        if container is not None:
            container.update_group_section(section, recursive=False)

        for child_sec in section.children:
            self.update_each_container_section(child_sec)