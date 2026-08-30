import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
})

export const fetchJson = async (url) => {
  const response = await api.get(url)
  return response.data
}
