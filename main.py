#!/usr/bin/env python

import sys
import math
import pygame
import random
from collections import defaultdict

pygame.init()

# The window size
WIDTH, HEIGHT = 600, 600
WIDTHD2, HEIGHTD2 = WIDTH/2., HEIGHT/2.
win=pygame.display.set_mode((WIDTH, HEIGHT))

# The number of simulated planets
PLANETS = 10

# The density of the planets - used to calculate their mass
# from their volume (i.e. via their radius)
DENSITY = 0.001

# The gravity coefficient - it's my universe, I can pick whatever I want :-)
GRAVITYSTRENGTH = 1.e4

TEXTFONT = pygame.font.SysFont("Brill", 20)
# The global list of planets
g_listOfPlanets = {}

class State:
    """Class representing position and velocity."""
    def __init__(self, x, y, vx, vy):
        self._x, self._y, self._vx, self._vy = x, y, vx, vy

    def __repr__(self):
        return 'x:{x} y:{y} vx:{vx} vy:{vy}'.format(
            x=self._x, y=self._y, vx=self._vx, vy=self._vy)


class Derivative:
    """Class representing velocity and acceleration."""
    def __init__(self, dx, dy, dvx, dvy):
        self._dx, self._dy, self._dvx, self._dvy = dx, dy, dvx, dvy

    def __repr__(self):
        return 'dx:{dx} dy:{dy} dvx:{dvx} dvy:{dvy}'.format(
            dx=self._dx, dy=self._dy, dvx=self._dvx, dvy=self._dvy)


class Planet:
    """Class representing a planet. The "_st" member is an instance of "State",
    carrying the planet's position and velocity - while the "_m" and "_r"
    members represents the planet's mass and radius."""
    def __init__(self):
        self._st = State(
           float(random.randint(0, WIDTH)),
           float(random.randint(0, HEIGHT)),
           float(random.randint(0, 300)/100.)-1.5,
           float(random.randint(0, 300)/100.)-1.5)
        self._r = 1.5
        planetNames = ['Venus', 'Earth', 'Mars', 'Mercury', 'Jupiter', 'Saturn']
        self.name = random.choice(planetNames)
        self.id = '' 
        self.setMassFromRadius()
        self._merged = False

    def __repr__(self):
        return repr(self._st)

    def acceleration(self, state, unused_t):
        """Calculate acceleration caused by other planets on this one."""
        ax = 0.0
        ay = 0.0
        for key, p in g_listOfPlanets.items():
            if p is self or p._merged:
                continue  # ignore ourselves and merged planets
            dx = p._st._x - state._x
            dy = p._st._y - state._y
            dsq = dx*dx + dy*dy  # distance squared
            dr = math.sqrt(dsq)  # distance
            force = GRAVITYSTRENGTH*self._m*p._m/dsq if dsq>1e-10 else 0.
            # Accumulate acceleration...
            ax += force*dx/dr
            ay += force*dy/dr
        return (ax, ay)

    def initialDerivative(self, state, t):
        """Part of Runge-Kutta method."""
        ax, ay = self.acceleration(state, t)
        return Derivative(state._vx, state._vy, ax, ay)

    def nextDerivative(self, initialState, derivative, t, dt):
        """Part of Runge-Kutta method."""
        state = State(0., 0., 0., 0.)
        state._x = initialState._x + derivative._dx*dt
        state._y = initialState._y + derivative._dy*dt
        state._vx = initialState._vx + derivative._dvx*dt
        state._vy = initialState._vy + derivative._dvy*dt
        ax, ay = self.acceleration(state, t+dt)
        return Derivative(state._vx, state._vy, ax, ay)

    def updatePlanet(self, t, dt):
        """Runge-Kutta 4th order solution to update planet's pos/vel."""
        a = self.initialDerivative(self._st, t)
        b = self.nextDerivative(self._st, a, t, dt*0.5)
        c = self.nextDerivative(self._st, b, t, dt*0.5)
        d = self.nextDerivative(self._st, c, t, dt)
        dxdt = 1.0/6.0 * (a._dx + 2.0*(b._dx + c._dx) + d._dx)
        dydt = 1.0/6.0 * (a._dy + 2.0*(b._dy + c._dy) + d._dy)
        dvxdt = 1.0/6.0 * (a._dvx + 2.0*(b._dvx + c._dvx) + d._dvx)
        dvydt = 1.0/6.0 * (a._dvy + 2.0*(b._dvy + c._dvy) + d._dvy)
        self._st._x += dxdt*dt
        self._st._y += dydt*dt
        self._st._vx += dvxdt*dt
        self._st._vy += dvydt*dt

    def setMassFromRadius(self):
        """From _r, set _m: The volume is (4/3)*Pi*(r^3)..."""
        self._m = DENSITY*4.*math.pi*(self._r**3.)/3.

    def setRadiusFromMass(self):
        """Reversing the setMassFromRadius formula, to calculate radius from
        mass (used after merging of two planets - mass is added, and new
        radius is calculated from this)"""
        self._r = (3.*self._m/(DENSITY*4.*math.pi))**(0.3333)

def drawText(text, font, textCol, x, y):
    img = font.render(text, False, textCol)
    win.blit(img, (x, y))


def main():
    clock = pygame.time.Clock()

    global g_listOfPlanets, PLANETS
    if len(sys.argv) == 2:
        PLANETS = int(sys.argv[1])

    # And God said: Let there be lights in the firmament of the heavens...
    g_listOfPlanets = {}
    for i in range(0, PLANETS):
        tempPlanet = Planet()
        g_listOfPlanets[i+1] = tempPlanet

    def planetsTouch(p1, p2):
        dx = p1._st._x - p2._st._x
        dy = p1._st._y - p2._st._y
        dsq = dx*dx + dy*dy
        dr = math.sqrt(dsq)
        return dr<=(p1._r + p2._r)

    sun = Planet()
    sun._st._x, sun._st._y = WIDTHD2, HEIGHTD2
    sun._st._vx = sun._st._vy = 0.
    sun._m *= 1000
    sun.setRadiusFromMass()
    sun.name = 'Sun'
    g_listOfPlanets[0] = sun
    for key, p in g_listOfPlanets.items():
        if p is sun:
            continue
        if planetsTouch(p, sun):
            p._merged = True  # ignore planets inside the sun

    paused = False
    focused = False
    focusID = ''
    zoom = 1.0
    cameraPosX = 0
    cameraPosY = 0
    # t and dt are unused in this simulation, but are in general, 
    # parameters of engine (acceleration may depend on them)
    t, dt = 0., 1

    bClearScreen = True
    pygame.display.set_caption('Gravity simulation (SPACE: show orbits, '
                               'keypad +/- : zoom in/out)')
    while True:
        clock.tick(30)
        t += dt
        pygame.display.flip()
        if bClearScreen:  # Show orbits or not?
            win.fill((0, 0, 0))
        win.lock()
        for key, p in g_listOfPlanets.items():
            if not p._merged:  # for planets that have not been merged, draw a
                # circle based on their radius, but take zoom factor into account
                pygame.draw.circle(win, (255, 255, 255),
                    (int(WIDTHD2+zoom*WIDTHD2*(p._st._x-WIDTHD2)/WIDTHD2 + cameraPosX),
                     int(HEIGHTD2+zoom*HEIGHTD2*(p._st._y-HEIGHTD2)/HEIGHTD2 + cameraPosY)),
                     int(p._r*zoom), 0)
        win.unlock()

        # Update all planets' positions and speeds (should normally double
        # buffer the list of planet data, but turns out this is good enough :-)
        for key, p in g_listOfPlanets.items():
            if p._merged or p is sun:
                continue
            # Calculate the contributions of all the others to its acceleration
            # (via the gravity force) and update its position and velocity
            if not paused:
                p.updatePlanet(t, dt)

        # See if we should merge the ones that are close enough to touch,
        # using elastic collisions (conservation of total momentum)
        for key, p1 in g_listOfPlanets.items():
            if p1._merged:
                continue
            for key, p2 in g_listOfPlanets.items():
                if p1 is p2 or p2._merged:
                    continue
                if planetsTouch(p1, p2):
                    if p1._m < p2._m:
                        p1, p2 = p2, p1  # p1 is the biggest one (mass-wise)
                    p2._merged = True
                    if p1 is sun:
                        continue  # No-one can move the sun :-)
                    newvx = (p1._st._vx*p1._m+p2._st._vx*p2._m)/(p1._m+p2._m)
                    newvy = (p1._st._vy*p1._m+p2._st._vy*p2._m)/(p1._m+p2._m)
                    p1._m += p2._m  # maintain the mass (just add them)
                    p1.setRadiusFromMass()  # new mass --> new radius
                    p1._st._vx, p1._st._vy = newvx, newvy

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    paused = not paused
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # on left click
                if event.button == 1:
                    mouse_x, mouse_y = event.pos
                    #might want to use enumerate() here to get rid of the focus index... maybe
                    for key, p in g_listOfPlanets.items():
                        if not p._merged:  # for planets that have not been merged, draw a
                            p_x_pos = int(WIDTHD2+zoom*WIDTHD2*(p._st._x-WIDTHD2)/WIDTHD2 + cameraPosX)
                            p_y_pos = int(HEIGHTD2+zoom*HEIGHTD2*(p._st._y-HEIGHTD2)/HEIGHTD2 + cameraPosY)
                            p_r_cur = p._r*zoom
                            print(p._st._y)

                            # if you click on a planet
                            if p_x_pos-p_r_cur < mouse_x < p_x_pos+p_r_cur and p_y_pos-p_r_cur < mouse_y < p_y_pos+p_r_cur: 
                                focused = True
                                focusID = key
                                print(focusID)
                                print(p.name)
                                break
                        focused = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            zoom /= 0.99
        if keys[pygame.K_s]:
            zoom /= 1.01
        # camera movement
        if focused == False:
            if keys[pygame.K_UP]:
                cameraPosY += 5
            if keys[pygame.K_DOWN]:
                cameraPosY -= 5
            if keys[pygame.K_RIGHT]:
                cameraPosX -= 5
            if keys[pygame.K_LEFT]:
                cameraPosX += 5
        else:
            cameraPosY = (g_listOfPlanets[focusID]._st._y - HEIGHTD2) * -1
            cameraPosX = (g_listOfPlanets[focusID]._st._x - WIDTHD2) * -1
            pygame.draw.rect(win, (255, 255, 255), (WIDTH-175, HEIGHT-575, 150, 300), 1)
            drawText(g_listOfPlanets[focusID].name, TEXTFONT, (255, 255, 255), 440, 35)
        if keys[pygame.K_ESCAPE]:
            break

if __name__ == "__main__":
    try:
        import psyco
        psyco.profile()
    except:
        print('Psyco not found, ignoring it')
    main()


