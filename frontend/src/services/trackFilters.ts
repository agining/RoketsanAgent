import type { AnalysisEntity } from '../types/analysis';

/** Active GPS tracks are evaluated by the API and are not rejected detections. */
export function isActiveTrackEntity(entity: AnalysisEntity) {
  return entity.source !== null && entity.vehicle?.filtered !== true;
}

export function activeTrackEntities(entities: AnalysisEntity[]) {
  return entities.filter(isActiveTrackEntity);
}
