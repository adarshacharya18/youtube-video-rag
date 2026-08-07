from src.animation.scenes.base_scene import MANIM_AVAILABLE, BaseDSAScene

if MANIM_AVAILABLE:
    import manim
    from manim import VGroup, Rectangle, Text, DOWN, RIGHT, UP

class StackQueueScene(BaseDSAScene):
    def construct_dsa_animation(self):
        if not MANIM_AVAILABLE:
            return

        action = self.params.get("action", "display")
        
        if action == "push":
            self.action_push()
        elif action == "pop":
            self.action_pop()
        elif action == "enqueue":
            self.action_enqueue()
        elif action == "dequeue":
            self.action_dequeue()
        else:
            self.action_display()

    def create_container(self, elements, ctype="stack"):
        group = VGroup()
        for val in elements:
            box = Rectangle(width=2, height=1, color=self.theme.BORDER, fill_color=self.theme.CONTAINER_BG, fill_opacity=1)
            t = Text(str(val), color=self.theme.TEXT_PRIMARY).scale(0.8)
            t.move_to(box.get_center())
            group.add(VGroup(box, t))
        
        if ctype == "stack":
            group.arrange(DOWN, buff=0)
        else:
            group.arrange(RIGHT, buff=0)
        return group

    def action_display(self):
        duration = float(self.params.get("duration", 5.0))
        elements = self.params.get("elements", [1, 2, 3])
        ctype = self.params.get("container_type", "stack")
        
        container = self.create_container(elements, ctype)
        self.play(manim.Create(container), run_time=duration * 0.8)
        self.wait(duration * 0.2)

    def action_push(self):
        duration = float(self.params.get("duration", 5.0))
        elements = self.params.get("elements", [1, 2])
        new_element = self.params.get("new_element", 3)
        
        container = self.create_container(elements, "stack")
        if len(elements) > 0:
            container.shift(DOWN * 0.5)
        self.play(manim.Create(container), run_time=duration * 0.4)
        
        new_item = self.create_container([new_element], "stack")
        if len(elements) > 0:
            new_item.next_to(container, UP, buff=0)
        self.play(manim.FadeIn(new_item, shift=DOWN), run_time=duration * 0.5)
        self.wait(duration * 0.1)

    def action_pop(self):
        duration = float(self.params.get("duration", 5.0))
        elements = self.params.get("elements", [1, 2, 3])
        
        container = self.create_container(elements, "stack")
        self.play(manim.Create(container), run_time=duration * 0.4)
        
        if len(container) > 0:
            top_item = container[0]
            self.play(manim.FadeOut(top_item, shift=UP), run_time=duration * 0.5)
        self.wait(duration * 0.1)

    def action_enqueue(self):
        duration = float(self.params.get("duration", 5.0))
        elements = self.params.get("elements", [1, 2])
        new_element = self.params.get("new_element", 3)
        
        container = self.create_container(elements, "queue")
        self.play(manim.Create(container), run_time=duration * 0.4)
        
        new_item = self.create_container([new_element], "queue")
        if len(elements) > 0:
            new_item.next_to(container, RIGHT, buff=0)
        self.play(manim.FadeIn(new_item, shift=manim.LEFT), run_time=duration * 0.5)
        self.wait(duration * 0.1)

    def action_dequeue(self):
        duration = float(self.params.get("duration", 5.0))
        elements = self.params.get("elements", [1, 2, 3])
        
        container = self.create_container(elements, "queue")
        self.play(manim.Create(container), run_time=duration * 0.4)
        
        if len(container) > 0:
            front_item = container[0]
            self.play(manim.FadeOut(front_item, shift=manim.LEFT), run_time=duration * 0.3)
            if len(container) > 1:
                rest = VGroup(*container[1:])
                self.play(rest.animate.shift(manim.LEFT * 2), run_time=duration * 0.2)
        self.wait(duration * 0.1)
