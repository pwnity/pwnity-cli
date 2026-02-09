---
description: How to add a new automation node to the Pwnity Web UI
---

# Adding a New Automation Node

This workflow describes the steps to create a new automation node component, ensuring it adheres to the project's design system and architecture.

## 1. Create the Node Component

Create a new Vue component in `src/components/automation/nodes/` (e.g., `MyNewNode.vue`).
Always use the `NodeTemplate` as the root element.

```vue
<template>
  <NodeTemplate
    node-type="MY_NODE_TYPE"
    :title="data?.label || 'My Node'"
    accent-color="#hexcode" 
    :selected="selected"
    :status="(data as any).status"
  >
    <!-- Icon Slot: Lucide icon representing the node -->
    <template #icon>
      <MyIcon :size="14" />
    </template>

    <!-- Body Content: Inputs and Outputs -->
    <div class="node-body-content">
      <!-- Inputs (Left aligned) -->
      <div class="port-group inputs">
        <div class="port trigger">
          <Handle type="target" :position="Position.Left" class="pwn-handle handle-trigger" id="trigger#execute" />
          <span class="port-label">execute</span>
        </div>
        <!-- Add more input ports here -->
      </div>

      <!-- Outputs (Right aligned) -->
      <div class="port-group outputs">
        <div class="port trigger">
          <span class="port-label">on_finish</span>
          <Handle type="source" :position="Position.Right" class="pwn-handle handle-trigger" id="trigger#on_finish" />
        </div>
        <!-- Add more output ports here -->
      </div>
    </div>

    <!-- Footer: Configuration Inputs (Optional) -->
    <template #footer>
      <div class="node-config">
        <!-- Your config inputs here -->
      </div>
    </template>
  </NodeTemplate>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { MyIcon } from 'lucide-vue-next'
import NodeTemplate from './NodeTemplate.vue'

defineProps<{
  data: {
    label?: string
    status?: string
    id?: string
    // Add other data properties
  }
  selected?: boolean
  edges?: any[]
}>()
</script>

<style scoped>
.node-body-content {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.port-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 80px;
}

.port-group.inputs { align-items: flex-start; }
.port-group.outputs { align-items: flex-end; text-align: right; }

.node-config {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
/* Add specific styles for footer inputs here */
</style>
```

**Key Guidelines:**
- **Accent Color:** Choose a unique hex color for your node type.
- **Port Labels:** Use lowercase labels for ports (e.g., `execute`, `data_in`, `stdout`).
- **Handles:** Use the global `.pwn-handle` class and specific type classes (e.g., `.handle-string`, `.handle-int`, `.handle-trigger`).
- **Status:** Pass `data.status` to `NodeTemplate` to handle badges automatically.

## 2. Register the Node

1. Open `src/components/automation/NodeEditor.vue`.
2. Import your new component:
   ```typescript
   import MyNewNode from './nodes/MyNewNode.vue'
   ```
3. Add it to the `nodeTypes` object:
   ```typescript
   const nodeTypes = {
     // ...
     my_type: markRaw(MyNewNode),
   }
   ```
4. Add a template slot in the `<VueFlow>` component:
   ```html
   <template #node-my_type="props">
     <MyNewNode v-bind="props" :edges="edges" />
   </template>
   ```

## 3. Verify

- Ensure the node appears correctly in the editor.
- Check that the header glass effect works (matches accent color).
- Verify input/output port alignment and labeling.
