# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Github-runner-image-builder-operator image relation observer."""

import logging
import typing

import ops

import builder
import charm_utils
import state

logger = logging.getLogger(__name__)


class ImageRelationData(typing.TypedDict, total=False):
    """Relation data for providing image ID.

    Other attributes map from image ID to comma separated tags.

    Attributes:
        id: The latest image ID to provide of the primary default image.
        tags: The comma separated tags of the image, e.g. x64, jammy, of the primary default image.
    """

    id: str
    tags: str


class Observer(ops.Object):
    """The image relation observer."""

    def __init__(self, charm: ops.CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "image-observer")
        self.charm = charm

        charm.framework.observe(
            charm.on[state.IMAGE_RELATION].relation_joined, self._on_image_relation_joined
        )

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_image_relation_joined(self, _: ops.RelationJoinedEvent) -> None:
        """Handle the image relation joined event."""
        build_config = state.BuilderRunConfig.from_charm(charm=self.charm)
        get_results = builder.get_latest_image(
            arch=build_config.arch,
            bases=build_config.bases,
            cloud_name=build_config.upload_cloud_name,
        )
        if not all(result.id for result in get_results):
            logger.warning("Not all images ready.")
            return
        self.update_image_data(results=get_results)

    def update_image_data(
        self, results: typing.Iterable[builder.BuildResult | builder.GetLatestImageResult]
    ) -> None:
        """Update the relation data if exists.

        Args:
            results: The build results from image builder.
        """
        for relation in self.model.relations[state.IMAGE_RELATION]:
            relation.data[self.model.unit].update(self._to_image_relation_data(results=results))

    def _to_image_relation_data(
        self, results: typing.Iterable[builder.BuildResult | builder.GetLatestImageResult]
    ) -> ImageRelationData:
        """Map build/fetch results to relation data.

        Args:
            results: The builder/fetch results.

        Raises:
            ValueError: If no builds were provided.

        Returns:
            image relation data mapping.
        """
        results = tuple(results)
        if len(results) < 1:
            raise ValueError("Builds output must be greater than 0.")
        primary_result = results[0]
        extra_results = results[1:]
        relation_data = ImageRelationData(
            id=primary_result.id,
            tags=self._get_tags(config=primary_result.config),
        )
        relation_data.update(
            # mypy does not understand that the update function for TypedDict can have dynamic keys
            # with total=False parameter.
            {  # type: ignore
                extra_result.id: self._get_tags(config=extra_result.config)
                for extra_result in extra_results
            }
        )
        return relation_data

    def _get_tags(self, config: builder.BuildConfig | builder.GetLatestImageConfig) -> str:
        """Get image tags from build/fetch config.

        Args:
            config: The arguments used to build/fetch the image.

        Returns:
            A comma separate image tags.
        """
        return ",".join([config.arch.value, config.base.value])
