<template>
  <div class="server-container">
    <el-row :gutter="20">
      <!-- Server Info Card -->
      <el-col :span="24" :md="12">
        <el-card>
          <template #header>
            <h3>服务器信息</h3>
          </template>
          <el-descriptions :column="1" border v-loading="infoLoading">
            <el-descriptions-item label="安装状态">
              <el-tag :type="serverInfo.installed ? 'success' : 'danger'">
                {{ serverInfo.installed ? '已安装' : '未安装' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="OpenVPN 版本">
              {{ serverInfo.version }}
            </el-descriptions-item>
            <el-descriptions-item label="服务状态">
              <el-tag :type="serverInfo.isRunning ? 'success' : 'danger'">
                {{ serverInfo.isRunning ? '运行中' : '已停止' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <div style="margin-top: 20px">
            <el-button type="warning" :icon="RefreshRight" @click="renewServer">
              续期服务器证书
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- Connected Clients Card -->
      <el-col :span="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <h3>在线客户端</h3>
              <el-button
                type="primary"
                size="small"
                :icon="Refresh"
                @click="loadStatus"
              >
                刷新
              </el-button>
            </div>
          </template>
          <el-table
            v-loading="statusLoading"
            :data="connectedClients"
            style="width: 100%"
            max-height="400"
          >
            <el-table-column prop="name" label="客户端" width="120" />
            <el-table-column prop="remote" label="远程地址" width="150" />
            <el-table-column prop="vpn_ip" label="VPN IP" width="120" />
            <el-table-column prop="connected_since" label="连接时间" />
            <el-table-column label="流量">
              <template #default="{ row }">
                <div style="font-size: 12px">
                  <div>↓ {{ row.bytes_received }}</div>
                  <div>↑ {{ row.bytes_sent }}</div>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="connectedClients.length === 0 && !statusLoading" class="no-data">
            暂无在线客户端
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, RefreshRight } from '@element-plus/icons-vue'
import api from '@/utils/api'

const infoLoading = ref(false)
const statusLoading = ref(false)
const serverInfo = ref({
  installed: false,
  version: 'Unknown',
  serviceStatus: 'inactive',
  isRunning: false
})
const connectedClients = ref([])

const loadServerInfo = async () => {
  infoLoading.value = true
  try {
    const response = await api.get('/server/info')
    serverInfo.value = response.data
  } catch (error) {
    ElMessage.error('加载服务器信息失败')
  } finally {
    infoLoading.value = false
  }
}

const loadStatus = async () => {
  statusLoading.value = true
  try {
    const response = await api.get('/server/status')
    connectedClients.value = response.data.clients || []
  } catch (error) {
    ElMessage.error('加载服务器状态失败')
  } finally {
    statusLoading.value = false
  }
}

const renewServer = () => {
  ElMessageBox.prompt('请输入证书有效期（天）', '续期服务器证书', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /^\d+$/,
    inputErrorMessage: '请输入有效的天数',
    inputValue: '3650'
  }).then(async ({ value }) => {
    try {
      await api.post('/server/renew', {
        certDays: parseInt(value)
      })
      ElMessage.success('服务器证书续期成功，请重启 OpenVPN 服务')
      loadServerInfo()
    } catch (error) {
      // Error handled by interceptor
    }
  })
}

onMounted(() => {
  loadServerInfo()
  loadStatus()
  
  // Auto refresh status every 60 seconds
  setInterval(() => {
    loadStatus()
  }, 60000)
})
</script>

<style scoped>
.server-container {
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

.no-data {
  text-align: center;
  color: #909399;
  padding: 20px;
}
</style>
