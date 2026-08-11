<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">楼宇 & 楼层管理</h2>
        <p class="text-sm text-slate-500">维护院区楼宇、楼层、房间与科室绑定关系（主数据，新就诊流程自动读取）</p>
      </div>
      <button @click="openCreateBuilding" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">+ 新建楼宇</button>
    </div>

    <div class="space-y-3">
      <div v-for="b in buildings" :key="b.building_id" class="bg-white rounded-xl shadow-sm overflow-hidden">
        <!-- 楼宇行 -->
        <div class="flex items-center px-4 py-3 bg-slate-50 border-b border-slate-100">
          <span class="font-semibold text-slate-800 flex-1">{{ b.name }}</span>
          <span class="text-xs text-slate-400 mr-3">{{ b.floors.length }}层</span>
          <button @click="openEditBuilding(b)" class="text-xs text-brand-600 hover:underline mr-3">重命名</button>
          <button @click="openAddFloor(b)" class="text-xs text-green-600 hover:underline mr-3">+ 楼层</button>
          <button @click="deleteBuilding(b)" class="text-xs text-red-600 hover:underline">删除</button>
        </div>
        <!-- 楼层列表 -->
        <div v-if="b.floors.length" class="divide-y divide-slate-50">
          <div v-for="f in b.floors" :key="f.floor_id" class="px-4 py-2">
            <div class="flex items-center">
              <span class="text-sm font-medium text-slate-700 flex-1">📍 {{ f.name }}</span>
              <span class="text-xs text-slate-400 mr-3">{{ f.rooms.length }}间</span>
              <button @click="openBindRoom(b, f)" class="text-xs text-green-600 hover:underline mr-3">+ 房间</button>
              <button @click="deleteFloor(b, f)" class="text-xs text-red-600 hover:underline">删除楼层</button>
            </div>
            <!-- 房间列表 -->
            <div v-if="f.rooms.length" class="flex flex-wrap gap-2 mt-2 ml-6">
              <span v-for="r in f.rooms" :key="r.room_id" class="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 rounded text-xs">
                {{ r.name }}
                <span class="text-slate-400">→ {{ r.dept_name }}</span>
                <button @click="deleteRoom(b, f, r)" class="text-red-500 hover:text-red-700 ml-1">✕</button>
              </span>
            </div>
          </div>
        </div>
        <div v-else class="px-4 py-3 text-sm text-slate-400">暂无楼层，点击「+ 楼层」添加</div>
      </div>
      <div v-if="!buildings.length" class="bg-white rounded-xl p-8 text-center text-slate-400">暂无楼宇</div>
    </div>

    <!-- 楼宇新建/重命名弹窗 -->
    <div v-if="showBuildingModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showBuildingModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">{{ editingBuilding ? '重命名楼宇' : '新建楼宇' }}</h3>
        <input v-model="buildingForm.name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="楼宇名称" />
        <div class="flex justify-end gap-2 mt-6">
          <button @click="showBuildingModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
          <button @click="saveBuilding" :disabled="saving" class="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 添加楼层弹窗 -->
    <div v-if="showFloorModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showFloorModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">添加楼层 → {{ targetBuilding?.name }}</h3>
        <input v-model="floorForm.name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="楼层名称（如 1层 / B1）" />
        <div class="flex justify-end gap-2 mt-6">
          <button @click="showFloorModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
          <button @click="saveFloor" :disabled="saving" class="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 绑定房间弹窗 -->
    <div v-if="showRoomModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showRoomModal = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">绑定房间 → {{ targetBuilding?.name }} / {{ targetFloor?.name }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm text-slate-600 mb-1">房间号</label>
            <input v-model="roomForm.room_name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500" placeholder="如 101诊室" />
          </div>
          <div>
            <label class="block text-sm text-slate-600 mb-1">归属科室</label>
            <select v-model="roomForm.dept_name" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500">
              <option v-for="d in departments" :key="d.dept_id" :value="d.name">{{ d.name }}</option>
            </select>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-6">
          <button @click="showRoomModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
          <button @click="saveRoom" :disabled="saving" class="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { adminApi } from '../../api/admin'

const buildings = ref([])
const departments = ref([])
const saving = ref(false)

const showBuildingModal = ref(false)
const editingBuilding = ref(false)
const buildingForm = reactive({ building_id: '', name: '' })

const showFloorModal = ref(false)
const targetBuilding = ref(null)
const floorForm = reactive({ name: '' })

const showRoomModal = ref(false)
const targetFloor = ref(null)
const roomForm = reactive({ room_name: '', dept_name: '' })

async function load() {
  const [b, d] = await Promise.all([adminApi.listBuildings(), adminApi.listDepartments()])
  buildings.value = b
  departments.value = d
}

// 楼宇
function openCreateBuilding() {
  editingBuilding.value = false
  buildingForm.building_id = ''
  buildingForm.name = ''
  showBuildingModal.value = true
}
function openEditBuilding(b) {
  editingBuilding.value = true
  buildingForm.building_id = b.building_id
  buildingForm.name = b.name
  showBuildingModal.value = true
}
async function saveBuilding() {
  saving.value = true
  try {
    if (editingBuilding.value) await adminApi.updateBuilding(buildingForm.building_id, buildingForm.name)
    else await adminApi.createBuilding(buildingForm.name)
    showBuildingModal.value = false
    await load()
  } catch (e) { alert(e.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}
async function deleteBuilding(b) {
  if (!confirm(`确认删除楼宇「${b.name}」及其所有楼层/房间？`)) return
  try { await adminApi.deleteBuilding(b.building_id); await load() }
  catch (e) { alert(e.response?.data?.detail || '删除失败') }
}

// 楼层
function openAddFloor(b) {
  targetBuilding.value = b
  floorForm.name = ''
  showFloorModal.value = true
}
async function saveFloor() {
  saving.value = true
  try {
    await adminApi.addFloor(targetBuilding.value.building_id, floorForm.name)
    showFloorModal.value = false
    await load()
  } catch (e) { alert(e.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}
async function deleteFloor(b, f) {
  if (!confirm(`确认删除楼层「${f.name}」？`)) return
  try { await adminApi.deleteFloor(b.building_id, f.floor_id); await load() }
  catch (e) { alert(e.response?.data?.detail || '删除失败') }
}

// 房间
function openBindRoom(b, f) {
  targetBuilding.value = b
  targetFloor.value = f
  roomForm.room_name = ''
  roomForm.dept_name = departments.value[0]?.name || ''
  showRoomModal.value = true
}
async function saveRoom() {
  saving.value = true
  try {
    await adminApi.bindRoom(targetBuilding.value.building_id, targetFloor.value.floor_id, { room_name: roomForm.room_name, dept_name: roomForm.dept_name })
    showRoomModal.value = false
    await load()
  } catch (e) { alert(e.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}
async function deleteRoom(b, f, r) {
  try { await adminApi.deleteRoom(b.building_id, f.floor_id, r.room_id); await load() }
  catch (e) { alert(e.response?.data?.detail || '删除失败') }
}

onMounted(load)
</script>
