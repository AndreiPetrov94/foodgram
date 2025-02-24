from django_filters.rest_framework import DjangoFilterBackend
from django.urls import reverse
from django.shortcuts import redirect
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.views.decorators.http import require_GET

from api.filters import IngredientFilter, RecipeFilter
# from api.pagination import CustomPagination
from rest_framework.pagination import LimitOffsetPagination
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    CustomUserSerializer,
    AvatarSerializer,
    SubscriptionSerializer,
    SubscriptionDetailSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeGetSerializer,
    RecipeCreateUpdateSerializer,
    FavoriteRecipeSerializer,
    ShoppingCartSerializer
)
from api.utils import get_shopping_cart
from recipes.models import (
    Tag,
    Recipe,
    Ingredient,
    Favorite,
    ShoppingCart
)
from users.models import User, Subscription


class CustomUserViewSet(UserViewSet):
    """Вьюсет для работы с пользователями и подписками."""

    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)

    # pagination_class = PageNumberPagination
    pagination_class = LimitOffsetPagination
    # pagination_class = CustomPagination

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=(IsAuthenticated,)
    )
    def me(self, request, *args, **kwargs):
        self.get_object = self.get_instance
        return self.retrieve(request, *args, **kwargs)

    @action(
        detail=False,
        methods=['PUT'],
        permission_classes=(IsAuthenticated,),
        url_path='me/avatar',
    )
    def avatar(self, request, *args, **kwargs):
        serializer = AvatarSerializer(
            instance=request.user,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @avatar.mapping.delete
    def delete_avatar(self, request, *args, **kwargs):
        user = self.request.user
        user.avatar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=('GET',),
        permission_classes=(IsAuthenticated,),
        url_path='subscriptions',
        url_name='subscriptions'
    )
    def subscriptions(self, request):
        user = request.user
        print(user)
        queryset = User.objects.filter(following__user=user)
        print(queryset)
        pages = self.paginate_queryset(queryset)
        serializer = SubscriptionDetailSerializer(
            pages,
            many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=(IsAuthenticated,)
    )
    def subscribe(self, request, id=None):
        user = request.user
        author = get_object_or_404(User, id=id)

        if user == author:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if self.request.method == 'POST':
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST)

            queryset = Subscription.objects.create(author=author, user=user)
            serializer = SubscriptionSerializer(
                queryset,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif self.request.method == 'DELETE':
            if not Subscription.objects.filter(
                    user=user,
                    author=author
            ).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST)

            subscription = get_object_or_404(
                Subscription,
                user=user,
                author=author
            )
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет тега."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет ингредиентов."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = None
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    search_fields = ('^name',)


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет для работы с рецептами."""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly,)
    # pagination_class = CustomPagination
    # pagination_class = PageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve', 'get-link'):
            return RecipeGetSerializer
        return RecipeCreateUpdateSerializer

    def create(self, request, *args, **kwargs):
        # Проверяем, авторизован ли пользователь
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Аутентификация требуется.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return super().create(request, *args, **kwargs)

    @action(
        detail=True,
        methods=['GET'],
        permission_classes=(AllowAny,),
        url_path='get-link',
        url_name='get-link'
    )
    def get_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        rev_link = reverse(
            'get_short_link',
            args=[recipe.pk]
        )
        return Response(
            {'short-link': request.build_absolute_uri(rev_link)},
            status=status.HTTP_200_OK
        )

    def check_recipe_action(self, request, model, serializer_class):
        recipe = self.get_object()
        user = request.user

        # if request.method == 'POST':
        #     obj, created = model.objects.get_or_create(
        #         user=user,
        #         recipe=recipe
        #     )
        #     data = serializer_class(recipe, context={'request': request}).data
        #     return Response(data, status=status.HTTP_201_CREATED)

        # obj = model.objects.filter(user=user, recipe=recipe).first()

        if request.method == 'POST':
            # Проверяем, существует ли уже запись
            if model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': f'Рецепт уже добавлен в {model.__name__.lower()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Создаем новую запись
            obj = model.objects.create(user=user, recipe=recipe)
            return Response(
                serializer_class(recipe, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )

        # if not obj:
        #     return Response(
        #         {'detail': 'Рецепт не найден.'},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        # obj.delete()
        # return Response(status=status.HTTP_204_NO_CONTENT)

        elif request.method == 'DELETE':
            # Удаляем запись, если она существует
            obj = model.objects.filter(user=user, recipe=recipe).first()
            if not obj:
                return Response(
                    {'detail': f'Рецепт не найден в {model.__name__.lower()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=(IsAuthenticated,)
    )
    def favorite(self, request, pk=None):
        return self.check_recipe_action(
            request,
            Favorite,
            FavoriteRecipeSerializer
        )

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=(IsAuthenticated,)
    )
    def shopping_cart(self, request, pk=None):
        return self.check_recipe_action(
            request,
            ShoppingCart,
            ShoppingCartSerializer
        )

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=(IsAuthenticated,)
    )
    def download_shopping_cart(self, request):
        return get_shopping_cart(request)


@require_GET
def get_short_link(request, pk):
    try:
        Recipe.objects.filter(pk=pk).exists()
        return redirect(f'/recipes/{pk}/')
    except Exception:
        raise ValidationError(f'Рецепт с id "{pk}" не найден.')
