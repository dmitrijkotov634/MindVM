from mindvm import EmuChunk, EmuDisplay, level_up

c = EmuChunk()
d = EmuDisplay(c)

road_stroke_y = c.var()
road_stroke_y2 = c.var()
road_stroke_y3 = c.var()

traffic_x = c.var()
traffic_y = c.var()
traffic_speed = c.var()

player_x = c.var()
points = c.var()

temp = c.var()

CAR_POSITION_1 = 47
CAR_POSITION_2 = 101

KEYBOARD = 497

skip_alloc = c.label()
c.jump(skip_alloc, c.NON_ZERO)

main_scene_shader = d.alloc_shader(
    d.SHADER_WRAP, d.CLEAR, points, 170, 0, d.SHADER_WRAP_END,
    d.COLOR, 0, 0, 0, 255, 0, 0,
    d.RECT, 38, 0, 100, d.DISPLAY_SIZE, 0, 0,
    d.COLOR, 255, 255, 255, 255, 0, 0,
    d.SHADER_WRAP, d.STROKE, 10, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 84, road_stroke_y, 8, 70, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 84, road_stroke_y2, 8, 70, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 84, road_stroke_y3, 8, 70, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.COLOR, 28, 28, 28, 255, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 0, road_stroke_y, 15, 70, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 161, road_stroke_y2, 15, 60, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.COLOR, 209, 200, 25, 255, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, player_x, 10, 29, 45, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.COLOR, 0, 130, 0, 230, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.POLY, 0, road_stroke_y3, 8, 50, 0, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.COLOR, 245, 111, 66, 255, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, traffic_x, traffic_y, 29, 45, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.FLUSH, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.SHADER_END, d.SHADER_WRAP_END
)

game_over_scene_shader = d.alloc_shader(
    d.SHADER_WRAP, d.COLOR, 0, 0, 0, 30, d.SHADER_WRAP_END,
    d.SHADER_WRAP,  d.RECT, 0, 0, d.DISPLAY_SIZE, d.DISPLAY_SIZE, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.COLOR, 255, 0, 0, 255, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 83, 25, 20, 20, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.RECT, 83, 55, 20, 96, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.FLUSH, d.SHADER_WRAP_END,
    d.SHADER_WRAP, d.SHADER_END, d.SHADER_WRAP_END
)

c.label(skip_alloc)

d.shader_map(0, main_scene_shader)
d.shader_map(1, game_over_scene_shader)

restart = c.label()

move_thread = c.label(reassign=True)
controls_thread = c.label(reassign=True)
render_thread = c.label(reassign=True)

c.goto_thread(3, controls_thread)
c.goto_thread(4, move_thread)
c.goto_thread(5, render_thread)

c[road_stroke_y] = 10
c[road_stroke_y2] = 100
c[road_stroke_y3] = 190

c[traffic_y] = 226
c[traffic_x] = CAR_POSITION_1
c[traffic_speed] = 2

c[player_x] = CAR_POSITION_2
c[points] = 0

c.fprint("CAR IO v", 1, ".", 1, "\nWAVECAT ", 2025)


def move_scene():
    c[road_stroke_y] -= 2
    c[road_stroke_y2] -= 2
    c[road_stroke_y3] -= 2

    q = c.label(reassign=True)
    c.jump_gt_const(q, road_stroke_y, -70)
    c[road_stroke_y] = 200
    c.label(q)

    q = c.label(reassign=True)
    c.jump_gt_const(q, road_stroke_y2, -70)
    c[road_stroke_y2] = 200
    c.label(q)

    q = c.label(reassign=True)
    c.jump_gt_const(q, road_stroke_y3, -70)
    c[road_stroke_y3] = 200
    c.label(q)


def move_traffic():
    c[traffic_y] -= traffic_speed

    q = c.label(reassign=True)
    c.jump_gt_const(q, traffic_y, -44)
    c[traffic_y] = 226
    c.math(c.store_int(c.OPERATION_IRAND), c.store_int(0), c.store_int(1), temp)
    c[traffic_x] = CAR_POSITION_1
    c[points] += 10
    c[traffic_speed] += 1
    c.jump(q, temp)
    c[traffic_x] = CAR_POSITION_2
    c.label(q)


collision_loop = c.label()


@level_up
def loop():
    q = c.label(reassign=True)
    c.math(c.store_int(c.OPERATION_NEQ), player_x, traffic_x, temp)
    c.jump(q, temp)
    c.jump_gt_const(q, traffic_y, 55)
    c.goto_thread(5, c.DISABLE_THREAD)
    c.goto_thread(4, c.DISABLE_THREAD)
    c[KEYBOARD + 4] = 0
    halt = c.label()
    d.shader_exec(1)
    c.fprint("GAME OVER\nYOU RECEIVE ", points, " POINTS\n")
    q2 = c.label()
    c.jump_neq_const(q2, KEYBOARD + 4, 1)
    c[KEYBOARD + 4] = 0
    c.jump(restart, c.NON_ZERO)
    c.label(q2)
    c.jump(halt, c.NON_ZERO)
    c.label(q)


c.jump(collision_loop, c.NON_ZERO)

c.label(controls_thread, inc_thread=True)


@level_up
def thread_3():
    controls_loop = c.label()
    q = c.label(reassign=True)
    c.jump_neq_const(q, KEYBOARD + 3, 1)
    c[KEYBOARD + 3] = 0
    c.jump_neq_const(q, player_x, CAR_POSITION_2)
    c[player_x] = CAR_POSITION_1
    c.label(q)

    q = c.label(reassign=True)
    c.jump_neq_const(q, KEYBOARD + 5, 1)
    c[KEYBOARD + 5] = 0
    c.jump_neq_const(q, player_x, CAR_POSITION_1)
    c[player_x] = CAR_POSITION_2
    c.label(q)
    c.jump(controls_loop, c.NON_ZERO)


c.label(move_thread, inc_thread=True)


@level_up
def thread_4():
    move_loop = c.label()
    move_scene()
    move_traffic()
    c.jump(move_loop, c.NON_ZERO)


c.label(render_thread, inc_thread=True)


@level_up
def thread_5():
    render_loop = c.label()
    d.shader_exec(0)
    c.jump(render_loop, c.NON_ZERO)


c.compile()
