from mindvm import EmuChunk, EmuDisplay, level_up

c = EmuChunk()
d = EmuDisplay(c, use_set_4=True)

red_thread = c.label()
green_thread = c.label()
blue_msg_thread = c.label()

c.goto_thread(3, red_thread)
c.goto_thread(4, green_thread)
c.goto_thread(5, blue_msg_thread)

r, g, b = c.var(999), c.var(888), c.var(777)

start = c.label(reassign=True)
c.jump(start, c.NON_ZERO)

shader = d.alloc_shader(
    d.CLEAR, 255, 0, 0, 0, 0, 0,
    d.COLOR, 255, 0, 0, 0, 0, 0,
    d.SHADER_WRAP, d.LINE, 0, 0, d.DISPLAY_SIZE, d.DISPLAY_SIZE, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.CLEAR, 0, 255, 0, d.SHADER_WRAP_END,
    d.FLUSH, 0, 0, 0, 0, 0, 0,
    d.SHADER_END, 11, 22, 33, 44, 55, 66
)

c.label(start)


@level_up
def main():
    d.shader_map(0, shader)
    q = c.label()
    d.shader_exec(0, with_accept=False)
    c.jump(q, c.NON_ZERO)


@level_up
def r():
    c.label(red_thread, inc_thread=True)
    red_loop = c.label()
    c.const_rand(255, r)
    c.jump(red_loop, c.NON_ZERO)


@level_up
def g():
    c.label(green_thread, inc_thread=True)
    green_loop = c.label()
    c.const_rand(255, g)
    c.jump(green_loop, c.NON_ZERO)


@level_up
def b_msg():
    c.label(blue_msg_thread, inc_thread=True)
    blue_msg_loop = c.label()
    c.const_rand(255, b)
    c.fprint("R=", r, ", G=", g, ", B=", b)
    c.jump(blue_msg_loop, c.NON_ZERO)


c.compile()
