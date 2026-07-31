import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SessionSidebar from './SessionSidebar.vue'

const sessions = [
  { id: 1, title: '会话一', message_count: 3, updated_at: '2026-07-31T12:00:00' },
  { id: 2, title: '会话二', message_count: 0, updated_at: '2026-07-30T09:00:00' },
]

describe('SessionSidebar', () => {
  it('renders sessions and highlights active', () => {
    const wrapper = mount(SessionSidebar, {
      props: { sessions, activeId: 2 },
      global: { plugins: [ElementPlus] },
    })
    const items = wrapper.findAll('.session-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('会话一')
    expect(items[0].text()).toContain('3 条')
    expect(items[1].classes()).toContain('active')
  })

  it('emits select, remove and create', async () => {
    const wrapper = mount(SessionSidebar, {
      props: { sessions },
      global: { plugins: [ElementPlus] },
    })
    await wrapper.findAll('.session-item')[1].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual([2])
    await wrapper.findAll('.item-del')[0].trigger('click')
    expect(wrapper.emitted('remove')[0]).toEqual([1])
    await wrapper.find('.add-btn').trigger('click')
    expect(wrapper.emitted('create')).toBeTruthy()
    await wrapper.find('.demo-btn').trigger('click')
    expect(wrapper.emitted('demo')).toBeTruthy()
  })

  it('shows empty state', () => {
    const wrapper = mount(SessionSidebar, {
      props: { sessions: [] },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.text()).toContain('暂无会话')
  })
})
