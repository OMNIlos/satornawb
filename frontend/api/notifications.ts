import { getNotifications } from '../src/features/notifications/repository.js'

export default function handler(_request: unknown, response: { status: (code: number) => { json: (data: unknown) => void } }) {
  response.status(200).json(getNotifications())
}
