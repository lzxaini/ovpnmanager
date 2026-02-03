<template>
  <div class="clients-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>客户端管理</h3>
          <el-button type="primary" :icon="Plus" @click="showAddDialog = true">
            添加客户端
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="clients"
        style="width: 100%"
        stripe
      >
        <el-table-column prop="name" label="客户端名称" width="150" fixed />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'valid' ? 'success' : 'danger'">
              {{ row.status === 'valid' ? '有效' : '已吊销' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="connected" label="连接状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.connected === 'yes' ? 'success' : 'info'">
              {{ row.connected === 'yes' ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="real_address" label="真实IP" width="150">
          <template #default="{ row }">
            {{ row.real_address || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="vpn_ip" label="VPN IP" width="120">
          <template #default="{ row }">
            {{ row.vpn_ip || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="流量统计" width="150">
          <template #default="{ row }">
            <div v-if="row.bytes_received">
              <div>↓ {{ formatBytes(row.bytes_received) }}</div>
              <div>↑ {{ formatBytes(row.bytes_sent) }}</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="connected_since" label="连接时间" width="160">
          <template #default="{ row }">
            {{ row.connected_since || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="expiry" label="过期时间" width="120" />
        <el-table-column prop="days_remaining" label="剩余天数" width="100">
          <template #default="{ row }">
            {{ row.days_remaining !== null ? row.days_remaining + ' 天' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="300" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              :icon="Download"
              @click="downloadConfig(row.name)"
            >
              下载配置
            </el-button>
            <el-button
              v-if="row.status === 'valid' && row.connected === 'yes'"
              type="warning"
              size="small"
              :icon="SwitchButton"
              @click="disconnectClient(row.name)"
            >
              强制下线
            </el-button>
            <el-button
              v-if="row.status === 'valid'"
              type="info"
              size="small"
              :icon="RefreshRight"
              @click="renewClient(row.name)"
            >
              续期
            </el-button>
            <el-button
              v-if="row.status === 'valid'"
              type="danger"
              size="small"
              :icon="Delete"
              @click="revokeClient(row.name)"
            >
              吊销
            </el-button>
            <el-button
              v-if="row.status === 'revoked'"
              type="danger"
              size="small"
              :icon="Delete"
              @click="deleteClient(row.name)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add Client Dialog -->
    <el-dialog
      v-model="showAddDialog"
      title="添加客户端"
      width="500px"
    >
      <el-form
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        label-width="100px"
      >
        <el-form-item label="客户端名称" prop="name">
          <el-input
            v-model="addForm.name"
            placeholder="只能包含字母、数字、下划线和连字符"
          />
        </el-form-item>
        <el-form-item label="密码保护">
          <el-switch v-model="addForm.usePassword" />
        </el-form-item>
        <el-form-item v-if="addForm.usePassword" label="密码" prop="password">
          <el-input
            v-model="addForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="证书有效期">
          <el-input-number
            v-model="addForm.certDays"
            :min="1"
            :max="36500"
          />
          <span style="margin-left: 10px">天</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAddClient">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Delete, RefreshRight, SwitchButton } from '@element-plus/icons-vue'
import api from '@/utils/api'

const loading = ref(false)
const clients = ref([])
const showAddDialog = ref(false)
const addLoading = ref(false)
const addFormRef = ref(null)

const addForm = ref({
  name: '',
  usePassword: false,
  password: '',
  certDays: 3650
})

const addRules = {
  name: [
    { required: true, message: '请输入客户端名称', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const loadClients = async () => {
  loading.value = true
  try {
    const response = await api.get('/clients')
    clients.value = response.data.clients || []
  } catch (error) {
    ElMessage.error('加载客户端列表失败')
  } finally {
    loading.value = false
  }
}

const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const handleAddClient = async () => {
  if (!addFormRef.value) return

  await addFormRef.value.validate(async (valid) => {
    if (!valid) return

    addLoading.value = true
    try {
      const data = {
        name: addForm.value.name,
        certDays: addForm.value.certDays
      }

      if (addForm.value.usePassword) {
        data.password = addForm.value.password
      }

      await api.post('/clients', data)
      ElMessage.success('客户端添加成功')
      showAddDialog.value = false
      addForm.value = { name: '', usePassword: false, password: '', certDays: 3650 }
      loadClients()
    } catch (error) {
      // Error handled by interceptor
    } finally {
      addLoading.value = false
    }
  })
}

const downloadConfig = async (name) => {
  try {
    const response = await api.get(`/clients/${name}/config`, {
      responseType: 'blob'
    })
    
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${name}.ovpn`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('配置文件下载成功')
  } catch (error) {
    ElMessage.error('配置文件下载失败')
  }
}

const revokeClient = (name) => {
  ElMessageBox.confirm(
    `确定要吊销客户端 "${name}" 吗？此操作不可撤销，已连接的客户端将立即断开连接。`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await api.delete(`/clients/${name}`)
      ElMessage.success('客户端吊销成功')
      loadClients()
    } catch (error) {
      // Error handled by interceptor
    }
  })
}

const renewClient = (name) => {
  ElMessageBox.prompt('请输入证书有效期（天）', '续期客户端', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /^\d+$/,
    inputErrorMessage: '请输入有效的天数',
    inputValue: '3650'
  }).then(async ({ value }) => {
    try {
      await api.post(`/clients/${name}/renew`, {
        certDays: parseInt(value)
      })
      ElMessage.success('客户端续期成功')
      loadClients()
    } catch (error) {
      // Error handled by interceptor
    }
  })
}

const disconnectClient = (name) => {
  ElMessageBox.confirm(
    `确定要强制断开客户端 "${name}" 的连接吗？`,
    '强制下线',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await api.post(`/clients/${name}/disconnect`)
      ElMessage.success('客户端已强制下线')
      // Reload clients to update connection status
      setTimeout(() => loadClients(), 1000)
    } catch (error) {
      // Error handled by interceptor
    }
  })
}

const deleteClient = (name) => {
  ElMessageBox.confirm(
    `确定要永久删除客户端 "${name}" 的证书文件吗？此操作不可恢复！`,
    '危险操作',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error',
      confirmButtonClass: 'el-button--danger'
    }
  ).then(async () => {
    try {
      await api.post(`/clients/${name}/delete`)
      ElMessage.success('客户端证书已永久删除')
      loadClients()
    } catch (error) {
      // Error handled by interceptor
    }
  }).catch(() => {
    // User cancelled
  })
}

onMounted(() => {
  loadClients()
  // Auto refresh every 30 seconds to update connection status
  setInterval(() => {
    loadClients()
  }, 30000)
})
</script>

<style scoped>
.clients-container {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
}
</style>
