<!--
Animated 3D force-directed graph for the "8.5 years, as a graph" slide.
Renders a readable, labelled slice of the real HealthGraph model — every
node carries its entity label (person name, device name, date, activity)
and every link carries its relationship type. Client-only: 3d-force-graph
(Three.js/WebGL) + three-spritetext are dynamically imported in onMounted
so the Slidev static build doesn't evaluate WebGL during SSR.

Sizing: a ResizeObserver keeps the renderer locked to the container box,
and the container is overflow:hidden — so the canvas can never spill out
over the rest of the slide.
-->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const COLOR: Record<string, string> = {
  Person: '#ec4899', Device: '#94a3b8', Workout: '#f59e0b', Day: '#10b981',
  DailySummary: '#38bdf8', SleepSession: '#6366f1', Week: '#a855f7',
}
const SIZE: Record<string, number> = {
  Person: 13, Device: 6, Workout: 5, Day: 6, DailySummary: 3.5, SleepSession: 5, Week: 8,
}

const PERSON = 'Matthias'
const DEVICES = ['iPhone 17 Pro', 'Apple Watch', 'Strava']
const ACTIVITIES = ['Running', 'Cycling', 'Strength', 'Swim', 'Hike', 'Rowing', 'Yoga']

const el = ref<HTMLDivElement>()
let graph: any = null
let raf = 0
let ro: ResizeObserver | null = null
const failed = ref(false)

/** Deterministic, readable slice of the real graph structure (~30 nodes). */
function buildSample() {
  const nodes: any[] = []
  const links: any[] = []
  const add = (id: string, type: string, label: string) => {
    nodes.push({ id, type, label, color: COLOR[type], val: SIZE[type] })
    return id
  }
  const link = (source: string, target: string, rel: string) =>
    links.push({ source, target, rel })

  add('person', 'Person', PERSON)
  DEVICES.forEach((d, i) => { add(`dev${i}`, 'Device', d); link('person', `dev${i}`, 'USES') })

  const DAYS = 9
  let prevDay: string | null = null
  let week: string | null = null
  let weekNo = 18
  for (let i = 0; i < DAYS; i++) {
    const day = add(`day${i}`, 'Day', `May ${7 + i}`)
    add(`sum${i}`, 'DailySummary', 'Summary')
    link(day, `sum${i}`, 'HAS_SUMMARY')
    if (prevDay) link(prevDay, day, 'NEXT_DAY')
    prevDay = day
    if (i === 0 || (7 + i) % 7 === 1) { weekNo++; week = add(`wk${weekNo}`, 'Week', `2026-W${weekNo}`) }
    if (week) link(day, week, 'PART_OF')
    if (i % 3 !== 2) {
      const act = ACTIVITIES[i % ACTIVITIES.length]
      const w = add(`w${i}`, 'Workout', act)
      link(w, day, 'ON_DAY')
      link(`dev${i % DEVICES.length}`, w, 'RECORDED')
      if (i === 3) {
        add(`sleep${i}`, 'SleepSession', 'Sleep')
        link(`sleep${i}`, day, 'ON_DAY')
        link(w, `sleep${i}`, 'FOLLOWED_BY')
      }
    }
  }
  return { nodes, links }
}

function fit() {
  if (!graph || !el.value) return
  const w = el.value.clientWidth
  const h = el.value.clientHeight
  if (w > 0 && h > 0) graph.width(w).height(h)
}

onMounted(async () => {
  if (!el.value) return
  try {
    const [{ default: ForceGraph3D }, { default: SpriteText }] = await Promise.all([
      import('3d-force-graph'),
      import('three-spritetext'),
    ])

    graph = ForceGraph3D()(el.value)
      .backgroundColor('rgba(0,0,0,0)')
      .graphData(buildSample())
      .nodeVal((n: any) => n.val)
      .nodeColor((n: any) => n.color)
      .nodeOpacity(0.9)
      .nodeResolution(14)
      .nodeThreeObjectExtend(true)
      .nodeThreeObject((n: any) => {
        // DailySummary is a secondary node — show it as a bare sphere so
        // the labels stay on the entities that matter (person, device,
        // date, workout, sleep, week).
        if (n.type === 'DailySummary') return false
        const t = new SpriteText(n.label)
        t.color = '#0f172a'
        t.backgroundColor = 'rgba(255,255,255,0.88)'
        t.padding = 2
        t.borderRadius = 3
        t.fontWeight = '600'
        t.textHeight = n.type === 'Person' ? 7.5 : 4.6
        t.position.y = (n.val ?? 5) + 7
        return t
      })
      .linkColor(() => 'rgba(110,122,145,0.4)')
      .linkWidth(0.5)
      .linkDirectionalParticles(2)
      .linkDirectionalParticleWidth(1.2)
      .linkDirectionalParticleSpeed(0.006)
      .linkThreeObjectExtend(true)
      .linkThreeObject((l: any) => {
        // No background pill — bare faint text reads cleanly on the
        // white slide without cluttering it with ~40 white rectangles.
        const t = new SpriteText(l.rel)
        t.color = 'rgba(100,116,139,0.75)'
        t.textHeight = 2.2
        return t
      })
      .linkPositionUpdate((sprite: any, { start, end }: any) => {
        sprite.position.set(
          start.x + (end.x - start.x) / 2,
          start.y + (end.y - start.y) / 2,
          start.z + (end.z - start.z) / 2,
        )
      })
      .enableNodeDrag(false)
      .showNavInfo(false)
    fit()

    // Keep the renderer locked to the container — never let it spill out.
    ro = new ResizeObserver(fit)
    ro.observe(el.value)

    // Let the force settle, frame the whole graph, then orbit at that distance.
    graph.cameraPosition({ z: 320 })
    setTimeout(() => {
      graph.zoomToFit(800, 60)
      setTimeout(() => {
        const c = graph.cameraPosition()
        const r = Math.hypot(c.x || 0, c.y || 0, c.z || 0) || 260
        const y = c.y || 30
        let angle = Math.atan2(c.x || 0, c.z || r)
        const orbit = () => {
          angle += 0.0013
          graph.cameraPosition({ x: r * Math.sin(angle), y, z: r * Math.cos(angle) })
          raf = requestAnimationFrame(orbit)
        }
        orbit()
      }, 950)
    }, 1500)
  } catch (e) {
    console.error('HealthGraph3D failed to init', e)
    failed.value = true
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  ro?.disconnect()
  try { graph?._destructor?.() } catch { /* noop */ }
})
</script>

<template>
  <div class="hg3d-wrap">
    <div ref="el" class="hg3d-canvas" />
    <div v-if="failed" class="hg3d-fallback">
      Person → Device → Workout → Day → SleepSession · DailySummary · Week
    </div>
  </div>
</template>

<style scoped>
.hg3d-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;       /* the canvas can never spill past this box */
}
.hg3d-canvas {
  width: 100%;
  height: 100%;
}
/* Purely decorative auto-orbit — let clicks pass through to slide nav. */
.hg3d-canvas :deep(canvas) {
  pointer-events: none;
}
.hg3d-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.8rem;
  opacity: 0.6;
}
</style>
