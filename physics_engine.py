import pymunk
import random
import time
import math


class Particle:
    """파티클 클래스"""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.elapsed = 0
        self.lifetime = 3000
        self.is_destroy = False

        force = random.random() * 250
        ang = math.radians(90 * random.random() - 180)
        self.fx = math.cos(ang) * force
        self.fy = math.sin(ang) * force
        self.hue = random.random() * 360

    def update(self, delta_time):
        self.elapsed += delta_time
        delta_x = self.fx * (delta_time / 100)
        delta_y = self.fy * (delta_time / 100)
        self.x += delta_x
        self.y += delta_y
        self.fy += (10 * delta_time) / 100

        if self.elapsed > self.lifetime:
            self.is_destroy = True

    def get_data(self):
        alpha = 1 - (self.elapsed / self.lifetime) ** 2
        return {
            'x': self.x,
            'y': self.y,
            'hue': self.hue,
            'alpha': alpha
        }


class ParticleManager:
    """파티클 매니저"""

    def __init__(self):
        self.particles = []

    def shot(self, x, y):
        for _ in range(200):
            self.particles.append(Particle(x, y))

    def update(self, delta_time):
        for particle in self.particles:
            particle.update(delta_time)
        self.particles = [p for p in self.particles if not p.is_destroy]

    def get_data(self):
        return [p.get_data() for p in self.particles]


class SkillEffect:
    """충격파 효과 (원본 skillEffect.ts)"""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = 0
        self.elapsed = 0
        self.lifetime = 500  # 0.5초
        self.is_destroy = False

    def update(self, delta_time):
        self.elapsed += delta_time
        self.size = (self.elapsed / self.lifetime) * 10
        if self.elapsed > self.lifetime:
            self.is_destroy = True

    def get_data(self):
        rate = self.elapsed / self.lifetime
        alpha = 1 - rate * rate
        return {
            'x': self.x,
            'y': self.y,
            'size': self.size,
            'alpha': alpha
        }


class PhysicsEngine:
    def __init__(self, names):
        self.space = pymunk.Space()
        self.space.gravity = (0, 10)
        self.space.iterations = 6
        self.space.sleep_time_threshold = float('inf')

        self.names = names
        self.marbles = []
        self.winners = []
        self.is_running = False
        self.GOAL_Y = 111
        self.camera_y = 20
        self.camera_target_y = 20
        self.camera_zoom = 10
        self.camera_target_zoom = 10

        self.particle_manager = ParticleManager()
        self.skill_effects = []  # 충격파 효과들
        self.winner_found = False

        self.create_map()
        self.create_marbles()

    def create_map(self):
        """맵 생성"""
        left_wall_points = [
            (9.25, -300), (9.25, 8.5), (2, 19.25), (2, 26),
            (9.75, 30), (9.75, 33.5), (1.25, 41), (1.25, 53.75),
            (8.25, 58.75), (8.25, 63), (9.25, 64), (8.25, 65),
            (8.25, 99.25), (15.1, 106.75), (15.1, 111.75)
        ]
        self.create_polyline(left_wall_points)

        right_wall_points = [
            (16.5, -300), (16.5, 9.25), (9.5, 20), (9.5, 22.5),
            (17.5, 26), (17.5, 33.5), (24, 38.5), (19, 45.5),
            (19, 55.5), (24, 59.25), (24, 63), (23, 64),
            (24, 65), (24, 100.5), (16, 106.75), (16, 111.75)
        ]
        self.create_polyline(right_wall_points)

        inner_zone1_points = [
            (12.75, 37.5), (7, 43.5), (7, 49.75), (12.75, 53.75), (12.75, 37.5)
        ]
        self.create_polyline(inner_zone1_points)

        inner_zone2_points = [
            (14.75, 37.5), (14.75, 43), (17.5, 40.25), (14.75, 37.5)
        ]
        self.create_polyline(inner_zone2_points)

        top_pins = [
            (15.5, 30.0), (15.5, 32), (15.5, 28),
            (12.5, 30), (12.5, 32), (12.5, 28)
        ]
        for x, y in top_pins:
            self.create_box(x, y, 0.2, 0.2, -math.pi / 4, restitution=1)

        diagonal_xs = [9.4, 11.3, 13.2, 15.1, 17, 18.9, 20.7, 22.7]
        for x in diagonal_xs:
            self.create_box(x, 66.6, 0.6, 0.1, math.pi / 4, restitution=0)

        for x in diagonal_xs:
            self.create_box(x, 69.1, 0.6, 0.1, -math.pi / 4, restitution=0)

        self.wheels = []
        wheel_data = [
            (8, 75, 3.5), (12, 75, -3.5), (16, 75, 3.5),
            (20, 75, -3.5), (24, 75, 3.5)
        ]
        for x, y, vel in wheel_data:
            wheel = self.create_rotating_box(x, y, 2, 0.1, vel)
            self.wheels.append(wheel)

        pin_y92_xs = [9.5, 12.75, 16, 19.25, 22.5]
        for x in pin_y92_xs:
            self.create_box(x, 92, 0.25, 0.25, 0.7853981633974483, restitution=0)

        pin_y95_xs = [11, 14.25, 17.5, 20.75]
        for x in pin_y95_xs:
            self.create_box(x, 95, 0.25, 0.25, 0.7853981633974483, restitution=0)

        for x in pin_y92_xs:
            self.create_box(x, 98, 0.25, 0.25, 0.7853981633974483, restitution=0)

        goal_wheel = self.create_rotating_box(14, 106.75, 2, 0.1, -1.2)
        self.wheels.append(goal_wheel)

    def create_polyline(self, points):
        body = self.space.static_body
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            segment = pymunk.Segment(body, p1, p2, 0.1)
            segment.friction = 0
            segment.elasticity = 0
            self.space.add(segment)

    def create_box(self, x, y, width, height, rotation, restitution=0):
        body = self.space.static_body
        hw = width
        hh = height
        vertices = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]

        cos_r = math.cos(rotation)
        sin_r = math.sin(rotation)
        rotated_vertices = []
        for vx, vy in vertices:
            rx = vx * cos_r - vy * sin_r + x
            ry = vx * sin_r + vy * cos_r + y
            rotated_vertices.append((rx, ry))

        poly = pymunk.Poly(body, rotated_vertices)
        poly.friction = 0
        poly.elasticity = restitution
        self.space.add(poly)

    def create_rotating_box(self, x, y, width, height, angular_velocity):
        moment = pymunk.moment_for_box(1, (width * 2, height * 2))
        body = pymunk.Body(1, moment, body_type=pymunk.Body.KINEMATIC)
        body.position = (x, y)
        body.angular_velocity = angular_velocity

        hw = width
        hh = height
        vertices = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        poly = pymunk.Poly(body, vertices)
        poly.friction = 0
        poly.elasticity = 0

        self.space.add(body, poly)
        return {'body': body, 'vel': angular_velocity}

    def create_marbles(self):
        for i, name in enumerate(self.names):
            x = 10.5 + (i % 10) * 0.6
            y = 5 - (i // 10) * 2
            hue = (360 / len(self.names)) * i

            mass = 1 + random.random()
            moment = pymunk.moment_for_circle(mass, 0, 0.25)
            body = pymunk.Body(mass, moment)
            body.position = (x, y)

            shape = pymunk.Circle(body, 0.25)
            shape.friction = 0
            shape.elasticity = 0

            self.space.add(body, shape)

            # ⭐ 원본과 동일한 weight 계산
            weight = 0.1 + (mass - 1)  # 0.1~1.1
            max_cooltime = 1000 + (1 - weight) * 4000  # 600~4600ms
            skill_rate = 0.05 * weight  # 0.02~0.22 (2%~22%)

            self.marbles.append({
                'body': body,
                'shape': shape,
                'name': name,
                'hue': hue,
                'finished': False,
                'cooltime': max_cooltime * random.random(),
                'max_cooltime': max_cooltime,
                'skill_rate': skill_rate
            })

    def start(self):
        self.is_running = True
        self.winner_found = False
        for marble in self.marbles:
            marble['body'].activate()

    def stop(self):
        self.is_running = False

    def apply_impact(self, source_marble):
        """충격파 발동"""
        src_pos = source_marble['body'].position

        for marble in self.marbles:
            if marble['finished'] or marble == source_marble:
                continue

            target_pos = marble['body'].position

            # 거리 계산
            dx = target_pos.x - src_pos.x
            dy = target_pos.y - src_pos.y
            dist_sq = dx * dx + dy * dy

            # 거리 100 이내에만 영향
            if dist_sq < 100:
                dist = math.sqrt(dist_sq)
                if dist > 0.01:
                    # 정규화
                    nx = dx / dist
                    ny = dy / dist

                    # 힘 계산
                    power = 1 - dist / 10
                    force = power * power * 5

                    # ⭐ 1.5배
                    impulse = (nx * force * 2, ny * force * 2)
                    marble['body'].apply_impulse_at_world_point(
                        impulse,
                        marble['body'].position
                    )

    def update(self):
        if not self.is_running:
            self.particle_manager.update(10)
            for effect in self.skill_effects:
                effect.update(10)
            self.skill_effects = [e for e in self.skill_effects if not e.is_destroy]
            return self.get_state()

        self.space.step(0.0125)

        for wheel in self.wheels:
            wheel['body'].angular_velocity = wheel['vel']

        # 구슬 업데이트 + 스킬
        for marble in self.marbles:
            if not marble['finished']:
                body = marble['body']
                vel = body.velocity
                speed = math.sqrt(vel.x ** 2 + vel.y ** 2)
                if speed < 0.5:
                    body.apply_impulse_at_local_point((random.uniform(-0.1, 0.1), 0.1))

                # 스킬 쿨타임 감소
                marble['cooltime'] -= 10

                # 쿨타임 끝나면 랜덤하게 Impact 스킬 발동
                if marble['cooltime'] <= 0:
                    if random.random() < marble['skill_rate']:
                        # 충격파 발동!
                        pos = marble['body'].position
                        self.skill_effects.append(SkillEffect(pos.x, pos.y))
                        self.apply_impact(marble)

                    # 쿨타임 리셋
                    marble['cooltime'] = marble['max_cooltime']

        # 골인 체크
        for marble in self.marbles:
            if marble['finished']:
                continue

            pos = marble['body'].position
            if pos.y > self.GOAL_Y:
                marble['finished'] = True
                self.space.remove(marble['body'], marble['shape'])

                self.winners.append({
                    'name': marble['name'],
                    'hue': marble['hue']
                })

                if len(self.winners) == len(self.marbles) and not self.winner_found:
                    self.particle_manager.shot(800, 400)
                    self.winner_found = True
                    self.is_running = False

        # 파티클 + 충격파 업데이트
        self.particle_manager.update(10)
        for effect in self.skill_effects:
            effect.update(10)
        self.skill_effects = [e for e in self.skill_effects if not e.is_destroy]

        # 카메라
        active_marbles = [m for m in self.marbles if not m['finished']]
        if active_marbles:
            lowest_y = max(m['body'].position.y for m in active_marbles)
            self.camera_target_y = min(lowest_y, self.GOAL_Y - 10)

            if lowest_y < 50:
                progress = lowest_y / 50.0
                self.camera_target_zoom = 10 + (progress * 5)
            elif lowest_y < 90:
                progress = (lowest_y - 50) / 40.0
                self.camera_target_zoom = 15 + (progress * 5)
            else:
                progress = (lowest_y - 90) / 21.0
                self.camera_target_zoom = 20 + (progress * 10)

        return self.get_state()

    def get_state(self):
        walls = []

        left_wall = [
            [9.25, -300], [9.25, 8.5], [2, 19.25], [2, 26],
            [9.75, 30], [9.75, 33.5], [1.25, 41], [1.25, 53.75],
            [8.25, 58.75], [8.25, 63], [9.25, 64], [8.25, 65],
            [8.25, 99.25], [15.1, 106.75], [15.1, 111.75]
        ]

        right_wall = [
            [16.5, -300], [16.5, 9.25], [9.5, 20], [9.5, 22.5],
            [17.5, 26], [17.5, 33.5], [24, 38.5], [19, 45.5],
            [19, 55.5], [24, 59.25], [24, 63], [23, 64],
            [24, 65], [24, 100.5], [16, 106.75], [16, 111.75]
        ]

        inner_zone1 = [
            [12.75, 37.5], [7, 43.5], [7, 49.75], [12.75, 53.75], [12.75, 37.5]
        ]

        inner_zone2 = [
            [14.75, 37.5], [14.75, 43], [17.5, 40.25], [14.75, 37.5]
        ]

        walls.append(left_wall)
        walls.append(right_wall)
        walls.append(inner_zone1)
        walls.append(inner_zone2)

        pins = []

        top_pins = [
            (15.5, 30.0), (15.5, 32), (15.5, 28),
            (12.5, 30), (12.5, 32), (12.5, 28)
        ]
        for x, y in top_pins:
            pins.append({'x': x, 'y': y, 'width': 0.2, 'height': 0.2, 'angle': -math.pi / 4})

        diagonal_xs = [9.4, 11.3, 13.2, 15.1, 17, 18.9, 20.7, 22.7]
        for x in diagonal_xs:
            pins.append({'x': x, 'y': 66.6, 'width': 0.6, 'height': 0.1, 'angle': math.pi / 4})

        for x in diagonal_xs:
            pins.append({'x': x, 'y': 69.1, 'width': 0.6, 'height': 0.1, 'angle': -math.pi / 4})

        pin_y92_xs = [9.5, 12.75, 16, 19.25, 22.5]
        for x in pin_y92_xs:
            pins.append({'x': x, 'y': 92, 'width': 0.25, 'height': 0.25, 'angle': 0.7853981633974483})

        pin_y95_xs = [11, 14.25, 17.5, 20.75]
        for x in pin_y95_xs:
            pins.append({'x': x, 'y': 95, 'width': 0.25, 'height': 0.25, 'angle': 0.7853981633974483})

        for x in pin_y92_xs:
            pins.append({'x': x, 'y': 98, 'width': 0.25, 'height': 0.25, 'angle': 0.7853981633974483})

        boxes = []
        for wheel in self.wheels:
            body = wheel['body']
            boxes.append({
                'x': body.position.x, 'y': body.position.y,
                'width': 2, 'height': 0.1, 'angle': body.angle
            })

        marbles_data = []
        for marble in self.marbles:
            if not marble['finished']:
                pos = marble['body'].position
                marbles_data.append({
                    'x': pos.x, 'y': pos.y,
                    'angle': marble['body'].angle,
                    'name': marble['name'], 'hue': marble['hue']
                })

        return {
            'walls': walls,
            'pins': pins,
            'boxes': boxes,
            'marbles': marbles_data,
            'winners': self.winners,
            'total_marbles': len(self.marbles),
            'particles': self.particle_manager.get_data(),
            'skill_effects': [e.get_data() for e in self.skill_effects],  # 충격파!
            'camera': {
                'targetY': self.camera_target_y,
                'targetZoom': self.camera_target_zoom
            }
        }