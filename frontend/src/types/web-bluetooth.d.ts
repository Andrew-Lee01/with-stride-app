// 최소한의 Web Bluetooth 타입 선언 (TS 기본 lib.dom.d.ts에 없음).
interface BluetoothLEScanFilter {
  namePrefix?: string
  services?: string[]
}

interface RequestDeviceOptions {
  acceptAllDevices?: boolean
  filters?: BluetoothLEScanFilter[]
  optionalServices?: string[]
}

interface BluetoothDevice {
  name?: string
  id: string
}

interface Bluetooth {
  requestDevice(options?: RequestDeviceOptions): Promise<BluetoothDevice>
}

interface Navigator {
  bluetooth: Bluetooth
}
