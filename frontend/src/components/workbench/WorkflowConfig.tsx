import { Settings2 } from 'lucide-react'
import type { WorkflowType } from '../../types'

interface Props {
  type: WorkflowType
  params: Record<string, string>
  onParamChange: (key: string, value: string) => void
}

const inputClass = "w-full rounded-lg border border-border-card bg-bg-primary/50 px-3 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/40 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30 transition-all"
const labelClass = "block text-sm font-medium text-text-secondary mb-1.5"

export function WorkflowConfig({ type, params, onParamChange }: Props) {
  const renderFields = () => {
    if (type === 'product_set') {
      return (
        <div className="space-y-4">
          <div>
            <label className={labelClass}>目标平台</label>
            <select className={inputClass} value={params.platform || ''}
                    onChange={e => onParamChange('platform', e.target.value)}>
              <option value="">通用电商平台</option>
              <option value="亚马逊">亚马逊</option>
              <option value="Temu">Temu</option>
              <option value="速卖通">速卖通</option>
              <option value="独立站">独立站</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>图片比例</label>
              <select className={inputClass} value={params.ratio || ''}
                      onChange={e => onParamChange('ratio', e.target.value)}>
                <option value="1:1">1:1 正方形</option>
                <option value="4:5">4:5 竖版</option>
                <option value="16:9">16:9 横版</option>
                <option value="3:4">3:4</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>语言</label>
              <select className={inputClass} value={params.language || ''}
                      onChange={e => onParamChange('language', e.target.value)}>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          <div>
            <label className={labelClass}>补充要求（选填）</label>
            <textarea className={inputClass} rows={3} value={params.requirements || ''}
                      onChange={e => onParamChange('requirements', e.target.value)}
                      placeholder="例如：清新高级风格，适合美妆品类..." />
          </div>
        </div>
      )
    }

    if (type === 'remove_bg') {
      return (
        <div>
          <label className={labelClass}>输出格式</label>
          <select className={inputClass} value={params.output_format || 'both'}
                  onChange={e => onParamChange('output_format', e.target.value)}>
            <option value="both">透明 PNG + 白底图</option>
            <option value="transparent">仅透明 PNG</option>
            <option value="white_bg">仅白底图</option>
          </select>
        </div>
      )
    }

    if (type === 'model') {
      return (
        <div className="space-y-4">
          <div>
            <label className={labelClass}>替换描述</label>
            <textarea className={inputClass} rows={3} value={params.replacement_desc || ''}
                      onChange={e => onParamChange('replacement_desc', e.target.value)}
                      placeholder="例如：将背景替换为海边沙滩场景，模特换为欧美风格..." />
          </div>
          <div>
            <label className={labelClass}>生成数量</label>
            <select className={inputClass} value={params.num_variants || '3'}
                    onChange={e => onParamChange('num_variants', e.target.value)}>
              <option value="1">1 张</option>
              <option value="2">2 张</option>
              <option value="3">3 张</option>
              <option value="4">4 张</option>
            </select>
          </div>
        </div>
      )
    }

    if (type === 'video') {
      return (
        <div className="space-y-4">
          <div>
            <label className={labelClass}>LLM 模型</label>
            <select className={inputClass} value={params.llm_model || 'DeepSeek-V4-Flash-Vision-Exp'}
                    onChange={e => onParamChange('llm_model', e.target.value)}>
              <option value="DeepSeek-V4-Flash-Vision-Exp">DeepSeek-V4-Flash-Vision-Exp</option>
              <option value="glm-4-flash">GLM-4-Flash</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>视频模型</label>
            <select className={inputClass} value={params.video_model || 'happyhorse-1.1-i2v'}
                    onChange={e => onParamChange('video_model', e.target.value)}>
              <option value="happyhorse-1.1-i2v">HappyHorse-1.1-i2v</option>
              <option value="happyhorse-1.0-r2v">HappyHorse-1.0-r2v</option>
              <option value="wan2.7">WAN 2.7</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>补充要求（选填）</label>
            <textarea className={inputClass} rows={3} value={params.requirements || ''}
                      onChange={e => onParamChange('requirements', e.target.value)}
                      placeholder="例如：希望视频呈现出温馨日系的风格..." />
          </div>
        </div>
      )
    }

    // edit
    return (
      <div>
        <label className={labelClass}>编辑指令</label>
        <textarea className={inputClass} rows={3} value={params.edit_instruction || ''}
                  onChange={e => onParamChange('edit_instruction', e.target.value)}
                  placeholder="例如：把背景换成白色，去掉水印，调亮画面..." />
      </div>
    )
  }

  return (
    <div className="glass rounded-2xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
          <Settings2 size={14} className="text-accent" />
        </div>
        <span className="text-sm font-medium text-text-primary">参数配置</span>
      </div>
      {renderFields()}
    </div>
  )
}