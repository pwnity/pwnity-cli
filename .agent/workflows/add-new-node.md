---
description: How to add a new automation node to the Pwnity Web UI
---

This workflow describes the process of creating and registering a new node type in the Pwnity Automation Editor.

## 1. Create the Node Component

Create a new Vue component in `src/components/automation/nodes/[NodeName]Node.vue`. This component must use the `<NodeTemplate>` wrapper.

**Important:** 
- Import `NodeTemplate` locally from `./NodeTemplate.vue`.
- You do NOT need to import `PwnDropdown`, `PwnInput`, or `PwnToggle` (they are global).
- **Design Rule:** Keep the node body clean. Do NOT include textual descriptions, placeholder texts, or info/help boxes in the node body. Rely on concise labels and intuitive UI controls.
- **Port Rule:** All port labels (Input and Output names) MUST be lowercase.

### Boilerplate Template

```vue
<template>
  <NodeTemplate
    node-type="[YOUR_TYPE]"
    title="[Display Title]"
    accent-color="#[HexColor]"
    :selected="selected"
    :status="statusLabel"
    :collapsed="data.collapsed"
    :node-id="id"
    :edges="edges"
    :data="data"
    trigger-in
    trigger-out
    @toggle-collapse="data.collapsed = !data.collapsed"
  >
    <!-- 1. Icon Slot -->
    <template #icon>
      <!-- Import an icon from lucide-vue-next -->
      <Zap :size="14" />
    </template>

    <!-- 2. Inputs Slot (Left side ports) -->
    <template #inputs>
      <div class="port data">
        <Handle 
          type="target" 
          :position="Position.Left" 
          class="pwn-handle handle-string" 
          id="string#input_name" 
        />
        <span class="port-label">input_name</span>
      </div>
    </template>

    <!-- 3. Outputs Slot (Right side ports) -->
    <template #outputs>
      <div class="port data">
        <span class="port-label">output_name</span>
        <Handle 
          type="source" 
          :position="Position.Right" 
          class="pwn-handle handle-string" 
          id="string#output_name" 
        />
      </div>
    </template>

    <!-- 4. Default Slot (Center Content) -->
    <div class="node-property">
      <span class="prop-label">CONFIGURATION</span>
      <PwnInput 
        v-model="data.some_value" 
        placeholder="Enter value..." 
        accent-color="#[HexColor]"
      />
    </div>

  </NodeTemplate>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position, useVueFlow } from '@vue-flow/core'
import { Zap } from 'lucide-vue-next'
import NodeTemplate from './NodeTemplate.vue'

const props = defineProps<{
  id: string
  selected?: boolean
  data: any
  edges?: any[]
}>()

// Helper for status classes (optional, NodeTemplate usually handles this via props.status)
const statusLabel = computed(() => {
  return props.data.status?.toUpperCase() || 'IDLE'
})
</script>
```

## 2. Register in `nodeRegistry.ts`

Open `src/utils/nodeRegistry.ts` and add a new entry to the `NODE_REGISTRY` object.

```typescript
[your_type_id]: {
    type: '[your_type_id]', // Must match node-type in component
    label: '[Display Label]',
    icon: [LucideIcon],
    category: '[triggers|inputs|utility|executables|logic|data]',
    description: '[Short description for the menu]',
    color: '#[HexColor]',
    ports: {
        // Format: 'type#name'
        inputs: ['trigger#on_start', 'string#input_name'],
        outputs: ['trigger#on_finish', 'string#output_name'],
        defaultInput: 'trigger#on_start',
        defaultOutput: 'trigger#on_finish'
    },
    // Optional: Default data
    initialData: { some_value: 'default' }
}
```

## 3. Register Component in `NodeEditor.vue`

Open `src/components/automation/NodeEditor.vue`:

1.  **Import** the component at the top:
    ```typescript
    import [NodeName]Node from './nodes/[NodeName]Node.vue'
    ```

2.  **Add to `nodeTypes` object**:
    ```typescript
    const nodeTypes = {
      // ... existing nodes
      [your_type_id]: markRaw([NodeName]Node)
    }
    ```

3.  **Add Template Reference**:
    Inside the `<VueFlow>` template, add a slot for your new node type:
    ```vue
    <template #node-[your_type_id]="props">
      <[NodeName]Node v-bind="props" :edges="edges" />
    </template>
    ```

## 4. Register in Backend (Python)

To ensure the backend can execute the new node type:

1.  **Create/Modify Logic**: Add your Python class (inherited from `BaseNode`) in `plugins/web_ui/automation_v2/nodes/`.
2.  **Register in Factory**: Open `plugins/web_ui/automation_v2/factory.py`:
    *   **Import** your node class from its module.
    *   **Add to `NODE_MAP`**:
        ```python
        NODE_MAP: Dict[str, Type[BaseNode]] = {
            # ... existing mappings
            '[your_type_id]': [YourNodeClass],
        }
        ```

## 5. Architectural Features (Automatic)

By following the categories in `nodeRegistry.ts`, the following features are activated automatically:

- **Validation Pipeline**: Nodes in `data` or `inputs` categories automatically appear as dots in the Dock's validation section.
- **Port Configuration**: Nodes in the `data` category (or the `parser` type) automatically show the **PORT CONFIG** tab in the Sidebar.
- **Execution Sequence**: Nodes in `executables`, `logic`, or `utility` categories appear in the Dock's execution sequence.

## 6. Status Synchronization (Crucial)

To ensure the node's health is correctly reflected in the Dock/Gallery, your component should synchronize its internal validation state with the `props.data.status` property.

Add this pattern to your `<script setup>`:

```typescript
const isInvalid = computed(() => {
  // Your validation logic (e.g. check if required fields are filled)
  return !props.data.required_field
})

// Sync status back to data so global UI components can react
watch(() => isInvalid.value, (invalid) => {
    if (props.data) {
        props.data.status = invalid ? 'invalid' : 'ready'
    }
}, { immediate: true })
```

## 7. Verify

1.  Reload the application.
2.  Open the Automation Editor.
3.  Right-click or drag from a handle to open the Quick Add Menu.
4.  Verify your new node appears in the correct category and can be dropped onto the canvas.
