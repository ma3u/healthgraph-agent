<!--
Animated 3D force-directed graph for the "8.5 years, as a graph" slide.
Renders a representative ~150-node slice of the real HealthGraph model
(7 node types, 7 relationship types) with flowing link particles and a
slow camera orbit. Client-only: 3d-force-graph (Three.js/WebGL) is
dynamically imported inside onMounted so the Slidev static build does
not try to evaluate it during SSR.
-->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const TYPES: Record<string, { color: string; val: number }> = {
  Person:       { color: '#ec4899', val: 14 },
  Device:       { color: '#94a3b8', val: 5 },
  Workout:      { color: '#f59e0b', val: 4 },
  Day:          { color: '#10b981', val: 5 },
  DailySummary: { color: '#38bdf8', val: 3.5 },
  SleepSession: { color: '#6366f1', val: 4 },
  Week:         { color: '#a855f7', val: 7 },
}

const el = ref<HTMLDivElement>()
let graph: any = null
let raf = 0
const failed = ref(false)

/** Deterministic representative slice of the real graph structure. */
function buildSample() {
  const nodes: any[] = []
  const links: any[] = []
  let seed = 42
  const rand = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296 }
  const add = (id: string, type: string) => {
    nodes.push({ id, type, color: TYPES[type].color, val: TYPES[type].val })
    return id
  }
  const link = (source: string, target: string, rel: string) => links.push({ source, target, rel })

  add('Person', 'Person')
  const devices = Array.from({ length: 6 }, (_, i) => add(`Device${i}`, 'Device'))
  devices.forEach(d => link('Person', d, 'USES'))

  const DAYS = 46
  let prevDay: string | null = null
  let week: string | null = null
  for (let i = 0; i < DAYS; i++) {
    const day = add(`Day${i}`, 'Day')
    link(day, add(`Sum${i}`, 'DailySummary'), 'HAS_SUMMARY')
    if (prevDay) link(prevDay, day, 'NEXT_DAY')
    prevDay = day
    if (i % 7 === 0) week = add(`Week${i / 7}`, 'Week')
    if (week) link(day, week, 'PART_OF')
    const nWorkouts = rand() < 0.68 ? 1 : rand() < 0.5 ? 2 : 0
    for (let w = 0; w < nWorkouts; w++) {
      const workout = add(`W${i}_${w}`, 'Workout')
      link(workout, day, 'ON_DAY')
      link(devices[Math.floor(rand() * devices.length)], workout, 'RECORDED')
      if (rand() < 0.16) {
        const sleep = add(`Sleep${i}_${w}`, 'SleepSession')
        link(sleep, day, 'ON_DAY')
        link(workout, sleep, 'FOLLOWED_BY')
      }
    }
  }
  return { nodes, links }
}

onMounted(async () => {
  if (!el.value) return
  try {
    const ForceGraph3D = (await import('3d-force-graph')).default
    graph = ForceGraph3D()(el.value)
      .backgroundColor('rgba(0,0,0,0)')
      .graphData(buildSample())
      .nodeColor((n: any) => n.color)
      .nodeVal((n: any) => n.val)
      .nodeOpacity(0.95)
      .nodeResolution(12)
      .linkColor(() => 'rgba(120,130,150,0.45)')
      .linkWidth(0.6)
      .linkDirectionalParticles(2)
      .linkDirectionalParticleWidth(1.3)
      .linkDirectionalParticleSpeed(0.005)
      .enableNodeDrag(false)
      .showNavInfo(false)
      .width(el.value.clientWidth)
      .height(el.value.clientHeight)
    graph.d3VelocityDecay(0.3)

    // Slow camera orbit so the graph reads as alive without interaction.
    let angle = 0
    const radius = 230
    const orbit = () => {
      angle += 0.0016
      graph.cameraPosition({
        x: radius * Math.sin(angle),
        y: 40 * Math.sin(angle * 0.5),
        z: radius * Math.cos(angle),
      })
      raf = requestAnimationFrame(orbit)
    }
    orbit()
  } catch (e) {
    console.error('HealthGraph3D failed to init', e)
    failed.value = true
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
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
}
.hg3d-canvas {
  width: 100%;
  height: 100%;
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
